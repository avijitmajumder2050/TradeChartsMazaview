FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ohlc_job.py .

ENTRYPOINT ["python", "ohlc_job.py"]
