# src/api/routes.py  (replace the loan_calculate() and keep the rest as-is)
from flask import Blueprint, jsonify, request
from ..utils.logging import get_logger
from ..services.volatility_client import get_metrics
from ..services.model_client import ModelClient
from ..services.loan_engine import per_asset_breakdown, portfolio_aggregate
from ..domain.risk_tiers import tier_info
from ..domain.errors import BadRequest

bp = Blueprint('api', __name__)
log = get_logger(__name__)
_model = ModelClient()

@bp.post('/loan/calculate')
def loan_calculate():
    print("Entered loan_calculate()")
    body = request.get_json(force=True, silent=True) or {}
    assets = body.get("assets") or []
    months = int(body.get("months") or 6)
    if not assets:
        raise BadRequest("assets is required")

    rows = []
    for a in assets:
        symbol = (a.get("symbol") or "").upper()
        alloc = float(a.get("allocation_usd") or 0)
        tier_req = a.get("tier")  # optional override
        if not symbol or alloc <= 0:
            raise BadRequest("asset symbol and positive allocation_usd required")

        # Business rule: USDT forced Tier 1 unless explicitly overridden
        if symbol == 'USDT' and not tier_req:
            tier, _ = ('Tier 1', 1.0)
        else:
            tier, _ = _model.risk_tier(symbol, {"hint": "loan_calculate"}) if not tier_req else (tier_req, 1.0)

        # Pull metrics for volatility premium + 24h column
        try:
            metrics = get_metrics(symbol)
        except Exception as e:
            log.warning(f"metrics fetch failed for {symbol}: {e}")
            metrics = {}

        row = per_asset_breakdown(alloc, tier, metrics, symbol)
        rows.append(row)

    summary = portfolio_aggregate(rows, months)

    profile = {
        "assets": rows,
        "summary": {**summary, "months": months}
    }
    return jsonify(profile)
