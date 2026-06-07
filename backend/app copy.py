"""
app.py
======
Flask REST API — Chart view only.

Endpoints
---------
GET  /api/health
GET  /api/tradingview/stocks
GET  /api/tradingview/stock_data?instrument_id=X
GET  /api/tradingview/refresh

Deploy : EC2 Docker  → port 5000
Frontend : S3 static → index.html
"""

import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import wraps

from tradingview_helper import get_stock_list, load_stock_data, refresh_live_data

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ── App ───────────────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ── Helper ────────────────────────────────────────────────────────────────────
def api_guard(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.exception("API error: %s", e)
            return jsonify({"success": False, "error": str(e)}), 500
    return wrapper

# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return jsonify({"success": True, "message": "Trading API is running"})

# ── Stock list ────────────────────────────────────────────────────────────────
@app.get("/api/tradingview/stocks")
@api_guard
def api_stocks():
    stocks = get_stock_list()
    return jsonify({"success": True, "stocks": stocks})

# ── Stock OHLCV ───────────────────────────────────────────────────────────────
@app.get("/api/tradingview/stock_data")
@api_guard
def api_stock_data():
    instrument_id = request.args.get("instrument_id", "").strip()
    if not instrument_id:
        return jsonify({"success": False, "error": "instrument_id is required"}), 400
    data = load_stock_data(instrument_id)
    if data is None:
        return jsonify({"success": False, "error": f"No data for {instrument_id}"}), 404
    return jsonify({"success": True, "data": data})

# ── Refresh ───────────────────────────────────────────────────────────────────
@app.get("/api/tradingview/refresh")
@api_guard
def api_refresh():
    result = refresh_live_data()
    return jsonify({"success": True, "instruments_updated": len(result)})

# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
