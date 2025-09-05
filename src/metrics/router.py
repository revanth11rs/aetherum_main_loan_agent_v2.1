# src/metrics/router.py
from flask import Blueprint, jsonify, Response
from .db import get_latest_metrics
from .cache import cache60

metrics_bp = Blueprint("metrics", __name__)

@metrics_bp.get("/<symbol>")
def get_metrics(symbol: str):
    sym = (symbol or "").upper()
    if not sym:
        return jsonify({"error": "symbol_required"}), 400

    # 1) cache first (60s)
    cached = cache60.get(sym)
    if cached is not None:
        return jsonify(cached), 200

    # 2) pull latest doc from Mongo
    doc = get_latest_metrics(sym)
    if not doc:
        # follow your “safe error” rule
        return jsonify({"error": f"No metrics found for {sym}"}), 404

    # 3) normalize BSON → JSON
    computed_at = None
    ca = doc.get("computed_at")
    if hasattr(ca, "isoformat"):
        computed_at = ca.isoformat()

    payload = {
        "symbol":           doc.get("symbol", sym),
        "name":             doc.get("name"),
        "pct_change_30d":   doc.get("30dChange(%)"),
        "pct_change_90d":   doc.get("90dChange(%)"),
        "volatility_score": doc.get("volatility_score"),
        "computed_at":      computed_at,
    }

    # 4) cache for 60s and return
    cache60.set(sym, payload)
    return jsonify(payload), 200
