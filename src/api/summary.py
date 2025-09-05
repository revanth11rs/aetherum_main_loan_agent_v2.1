# src/api/summary.py

from __future__ import annotations
from flask import Blueprint, request, jsonify

from ..services.summary_service import build_analyst_summary

bp = Blueprint("summary_api", __name__)

@bp.post("/loan/summary")
def loan_summary():
    """
    POST /loan/summary
    Body: either the full calculation output from /loan/calculate,
          or an object with a key "calculation" that contains it.

    Returns: { markdown, provider, model, used_llm }
    """
    payload = request.get_json(silent=True) or {}
    calc_out = payload.get("calculation") or payload
    if not isinstance(calc_out, dict) or "summary" not in calc_out:
        return jsonify({"error": "expected calculation output (must include 'summary')"}), 400

    res = build_analyst_summary(calc_out)
    return jsonify(res), 200
