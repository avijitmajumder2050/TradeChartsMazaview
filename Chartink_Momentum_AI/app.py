import datetime
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from flask import Flask, abort, jsonify, render_template, request

import chartink_momentum as momentum_mod
import chartink_momentum_backtest as momentum_backtest_mod
import chartink_stoch_backtest as stoch_mod
import mock_data
from connectors import ai_verdict, fundamentals_connector, ipo_connector, marketsmith_connector, news_connector

app = Flask(__name__)


# ============================================================
# COLUMN / STAT HELPERS
# ============================================================

def _stat(label, value):
    return {"label": label, "value": value}


def _col(key, label, type_="text"):
    return {"key": key, "label": label, "type": type_}


# ============================================================
# SCANNER RUNNERS
#
# Each of these calls straight into the existing scanner
# scripts' functions - the backend re-runs the live Chartink
# request every time a scanner is selected, nothing here is
# precomputed or cached to disk for display purposes.
# ============================================================

def run_stoch():

    backtest_df = stoch_mod.get_backtest()
    live_df = stoch_mod.get_live_scan()

    if backtest_df is None or live_df is None:
        raise RuntimeError("Chartink did not return scanner data")

    combined_df = stoch_mod.combine_live_and_backtest(
        live_df, backtest_df, days=10
    )

    rows = []

    if not combined_df.empty:
        rows = combined_df.rename(
            columns={"Backtest_Dates_Last_10": "BacktestDates"}
        ).to_dict(orient="records")

    return {
        "stats": [_stat("Match", len(live_df))],
        "columns": [
            _col("Stock", "Stock"),
            _col("In_Live_Scan_Today", "In Live Scan", "bool"),
            _col("BacktestDates", "Backtest Dates (Last 10 Days)"),
        ],
        "rows": rows,
    }


def run_momentum():

    df = momentum_mod.get_momentum_stocks()

    if df is None:
        raise RuntimeError("Chartink did not return scanner data")

    keep = [
        column
        for column in ("nsecode", "name", "close", "per_chg", "volume")
        if column in df.columns
    ]

    rows = df[keep].to_dict(orient="records") if not df.empty else []

    return {
        "stats": [_stat("Match", len(df))],
        "columns": [
            _col("nsecode", "Symbol"),
            _col("name", "Name"),
            _col("close", "Close", "num"),
            _col("per_chg", "% Chg", "pct"),
            _col("volume", "Volume", "num"),
        ],
        "rows": rows,
    }


def run_momentum_backtest():

    df = momentum_backtest_mod.get_backtest()

    if df is None:
        raise RuntimeError("Chartink did not return backtest data")

    rows = (
        df.sort_values("Date", ascending=False).to_dict(orient="records")
        if not df.empty else []
    )

    return {
        "stats": [
            _stat("Signals", len(df)),
            _stat("Days", int(df["Date"].nunique()) if not df.empty else 0),
        ],
        "columns": [
            _col("Date", "Date"),
            _col("Stock", "Stock"),
            _col("Stock_Count", "Stocks That Day", "num"),
        ],
        "rows": rows,
    }


SCANNERS = {
    "stoch": {
        "name": "Stochastic Crossover",
        "description": (
            "%K/%D(4,3) cross above 20, RSI(14) below 50, close below "
            "EMA(50) — live scan combined with the last 10 backtest days"
        ),
        "run": run_stoch,
    },
    "momentum": {
        "name": "Weekly Momentum Breakout",
        "description": (
            "Weekly EMA20 > EMA50 > EMA10, EMA100 > EMA200 stacked, "
            "price within 10% of the 20-week high, market cap > 2000cr"
        ),
        "run": run_momentum,
    },
    "momentum_backtest": {
        "name": "Weekly Momentum — Backtest History",
        "description": (
            "Historical trade dates for the weekly momentum breakout "
            "condition"
        ),
        "run": run_momentum_backtest,
    },
}


# ============================================================
# PAGES
# ============================================================

@app.route("/")
def home():
    return render_template("home.html", **mock_data.home_data())


@app.route("/scanner")
def scanner_page():

    selected_id = request.args.get("id", "")

    if selected_id not in SCANNERS:
        selected_id = ""

    return render_template(
        "scanner.html",
        scanners=SCANNERS,
        selected_id=selected_id,
    )


@app.route("/news")
def news():
    try:
        data = news_connector.get_news_data()
        # gainers/losers need a live quotes feed, not a news connector concern
        data["gainers"] = mock_data.news_data()["gainers"]
        data["losers"] = mock_data.news_data()["losers"]
    except Exception:
        app.logger.exception("news connector failed")
        data = {"stories": [], "trending": [], "gainers": [], "losers": [], "unavailable": True}
    return render_template("news.html", **data)


@app.route("/capabilities")
def capabilities():
    return render_template("capabilities.html", **mock_data.capabilities_data())


@app.route("/education")
def education():
    return render_template("education.html", **mock_data.education_data())


@app.route("/pricing")
def pricing():
    return render_template("pricing.html", **mock_data.pricing_data())


@app.route("/vision")
def vision():
    return render_template("vision.html", **mock_data.vision_data())


@app.route("/markets/ipo-hub")
def ipo_hub():
    try:
        data = ipo_connector.get_ipo_hub_data()
    except Exception:
        app.logger.exception("IPO connector failed")
        data = {"ipos": [], "subCategories": [], "unavailable": True}
    return render_template("ipo_hub.html", **data)


def _normalize_symbol(raw):
    # NSE/BSE tickers never contain spaces, so "HDFC Bank" -> "HDFCBANK"
    # and "TATA STEEL" -> "TATASTEEL" resolve correctly on screener.in
    # even though users naturally type the company name with spaces.
    return (raw or "HDFCBANK").strip().upper().replace(" ", "")


@app.route("/markets/research")
def research():
    symbol = _normalize_symbol(request.args.get("symbol"))
    try:
        data = fundamentals_connector.get_research_data(symbol)
        # same screener.in page backs both, so this reads from cache rather
        # than triggering a second fetch (see fundamentals_connector._get_raw)
        data.update(fundamentals_connector.get_fundamentals_data(symbol))
    except RuntimeError:
        return render_template("research.html", symbol=symbol, not_found=True)
    except Exception:
        app.logger.exception("fundamentals connector failed for %s", symbol)
        return render_template("research.html", symbol=symbol, unavailable=True)

    try:
        data.update(marketsmith_connector.get_strength_ratings(symbol))
    except Exception:
        # best-effort supplementary rating, not core to the page
        app.logger.exception("marketsmith connector failed for %s", symbol)

    try:
        data["aiVerdict"] = ai_verdict.get_verdict(
            symbol,
            data.get("header", {}),
            data.get("fundamentals", []),
            data.get("ratios", []),
            data.get("epsStrength"),
            data.get("priceStrength"),
        )
    except Exception:
        # best-effort — page works fine without the AI summary
        app.logger.exception("AI verdict generation failed for %s", symbol)

    return render_template("research.html", **data)


@app.route("/markets/chart")
def chart_page():
    symbol = request.args.get("symbol", "HDFCBANK")
    return render_template("chart.html", **mock_data.chart_data(symbol))


@app.route("/login")
def login():
    return render_template("login.html")


@app.route("/payment")
def payment():
    return render_template("payment.html")


@app.route("/dashboard")
def subscriber_dashboard():
    return render_template("subscriber_dashboard.html", **mock_data.subscriber_dashboard_data())


@app.route("/admin")
def admin_dashboard():
    return render_template("admin_dashboard.html", **mock_data.admin_dashboard_data())


# ============================================================
# API
# ============================================================

@app.get("/api/scanners")
def api_scanners():

    return jsonify([
        {"id": sid, "name": s["name"], "description": s["description"]}
        for sid, s in SCANNERS.items()
    ])


@app.get("/api/scanners/<scanner_id>/run")
def api_run_scanner(scanner_id):

    scanner = SCANNERS.get(scanner_id)

    if scanner is None:
        abort(404, description=f"Unknown scanner: {scanner_id}")

    try:
        result = scanner["run"]()
    except Exception as exc:
        return jsonify({
            "scanner_id": scanner_id,
            "scanner_name": scanner["name"],
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "error": str(exc),
        }), 502

    result["scanner_id"] = scanner_id
    result["scanner_name"] = scanner["name"]
    result["generated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    result["error"] = None

    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
