import os
import time
import logging
import boto3
import pandas as pd
from datetime import datetime, timedelta
import pytz
from dhanhq import DhanContext, dhanhq
from aws_s3 import S3_BUCKET as ACTIVE_S3_BUCKET

# -----------------------------
# CONFIG
# -----------------------------
AWS_REGION = "ap-south-1"

S3_BUCKET = ACTIVE_S3_BUCKET
MAPPING_KEY = "uploads/mapping.csv"
OUTPUT_PREFIX = "eod_data/"

EXCHANGE_SEGMENT = "NSE_EQ"
INSTRUMENT_TYPE = "EQUITY"

# -----------------------------
# Logging
# -----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# -----------------------------
# AWS Clients
# -----------------------------
ssm = boto3.client("ssm", region_name=AWS_REGION)
s3 = boto3.client("s3", region_name=AWS_REGION)

# -----------------------------
# Helpers
# -----------------------------
def get_param(name, decrypt=False):
    return ssm.get_parameter(
        Name=name,
        WithDecryption=decrypt
    )["Parameter"]["Value"]

def load_mapping():
    obj = s3.get_object(Bucket=S3_BUCKET, Key=MAPPING_KEY)
    return pd.read_csv(obj["Body"])[["Stock Name", "Instrument ID"]].dropna()

def upload_to_s3(local_path, s3_key):
    s3.upload_file(local_path, S3_BUCKET, s3_key)

# -----------------------------
# Main Logic
# -----------------------------
def fetch_daily_ohlc():
    try:
        access_token = get_param("/dhan/access_token", True)
        client_id = get_param("/dhan/client_id")

        dhan = dhanhq(DhanContext(client_id, access_token))
        logging.info("✅ Connected to DHAN API")
    except Exception as e:
        logging.error(f"❌ DHAN init failed: {e}")
        return

    try:
        df_symbols = load_mapping()
        logging.info(f"📄 Loaded {len(df_symbols)} stocks from S3 mapping.csv")
    except Exception as e:
        logging.error(f"❌ Failed to read mapping.csv: {e}")
        return

    to_date = datetime.today().strftime("%Y-%m-%d")
    from_date = (datetime.today() - timedelta(days=300)).strftime("%Y-%m-%d")

    india_tz = pytz.timezone("Asia/Kolkata")

    for _, row in df_symbols.iterrows():
        name = row["Stock Name"]
        instrument_id = int(row["Instrument ID"])

        try:
            response = dhan.historical_daily_data(
                security_id=instrument_id,
                exchange_segment=EXCHANGE_SEGMENT,
                instrument_type=INSTRUMENT_TYPE,
                from_date=from_date,
                to_date=to_date
            )

            if response.get("status") != "success":
                logging.warning(f"⚠ Failed: {name}")
                continue

            data = response["data"]
            dates = (
                pd.to_datetime(data["timestamp"], unit="s")
                .tz_localize("UTC")
                .tz_convert(india_tz)
                .date
            )

            df = pd.DataFrame({
                "date": dates,
                "open": data["open"],
                "high": data["high"],
                "low": data["low"],
                "close": data["close"],
                "volume": data["volume"]
            })

            local_file = f"/tmp/{instrument_id}.csv"
            s3_key = f"{OUTPUT_PREFIX}{instrument_id}.csv"

            df.to_csv(local_file, index=False)
            upload_to_s3(local_file, s3_key)

            logging.info(f"✅ {name} → s3://{S3_BUCKET}/{s3_key}")

            time.sleep(1)

        except Exception as e:
            logging.error(f"❌ Error for {name}: {e}")

# -----------------------------
if __name__ == "__main__":
    fetch_daily_ohlc()
