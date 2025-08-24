# src/services/loan_engine.py
from typing import List, Dict, Optional
from decimal import Decimal, ROUND_HALF_UP
from ..domain.risk_tiers import tier_info

# Base/Federal rate (6.33% as a fraction)
BASE_RATE = 0.0633

def fmt(x: float, places: str = '0.01') -> float:
    """Round to given decimal places (as string pattern) using bankers' rounding."""
    return float(Decimal(x).quantize(Decimal(places), rounding=ROUND_HALF_UP))

def _get_pct_change_30d(metrics: Dict) -> Optional[float]:
    """
    Pull 30d % change from metrics with robust key fallback:
      - "pct_change_30d"  (preferred for now)
    Returns float or None if not present/parseable.
    """
    v = (
        metrics.get("pct_change_30d")
        or metrics.get("pct_change_30")
        or metrics.get("30dChange(%)")
    )
    try:
        return float(v)
    except Exception:
        return None

def volatility_premium_from_metrics(metrics: Dict) -> float:
    """
    Volatility premium based on absolute **30-day** % change.
      |30d| < 10%   -> +1.0%
      10%–<20%      -> +1.5%
      >=20%         -> +2.0%
    If missing, default to +1.0%.
    """
    ch30 = _get_pct_change_30d(metrics)
    print(f"30d % change for volatility premium: {ch30}")
    if ch30 is None:
        return 0.01
    ch30 = abs(ch30)
    if ch30 < 10:   return 0.01
    if ch30 < 20:   return 0.015
    return 0.02

def interest_components_for_asset(tier: str, metrics: Dict) -> Dict[str, float]:
    """
    Return each interest piece separately (fractions), and the sum:
      - base_rate
      - risk_premium
      - volatility_premium
      - interest_rate (total = base + risk + vol)
    """
    info = tier_info(tier)
    base = BASE_RATE
    risk = info["risk_premium"]
    vol  = volatility_premium_from_metrics(metrics)
    total = base + risk + vol
    # keep a few more decimals in the rate fields; UI can format as %
    return {
        "base_rate": fmt(base, '0.0001'),
        "risk_premium": fmt(risk, '0.0001'),
        "volatility_premium": fmt(vol, '0.0001'),
        "interest_rate": fmt(total, '0.0001'),
    }

def per_asset_breakdown(alloc_usd: float, tier: str, metrics: Dict, symbol: str) -> Dict:
    """
    Build the per-asset view used by the UI and portfolio aggregation.
    Uses 30d % change (not 24h) for volatility premium and UI display.
    """
    # LTV from tier table
    ltv = tier_info(tier)["ltv"]

    # components + total
    ic = interest_components_for_asset(tier, metrics)

    loan_amount = alloc_usd * ltv
    return {
        "symbol": symbol,
        "tier": tier,
        "ltv": ltv,
        # interest pieces (fractions)
        "base_rate": ic["base_rate"],
        "risk_premium": ic["risk_premium"],
        "volatility_premium": ic["volatility_premium"],
        "interest_rate": ic["interest_rate"],   # total = base + risk + vol
        # money-ish
        "collateral_usd": fmt(alloc_usd),
        "loan_usd": fmt(loan_amount),
        # helpful for UI: surface the 30d change we used
        "pct_change_30d": _get_pct_change_30d(metrics),
    }

def portfolio_aggregate(rows: List[Dict], months: int) -> Dict:
    total_collateral = sum(r["collateral_usd"] for r in rows)
    total_loan = sum(r["loan_usd"] for r in rows)

    # weighted LTV
    weighted_ltv = (total_loan / total_collateral) if total_collateral else 0.0

    # weighted interest by loan share, using the *total* interest_rate we returned
    weighted_ir = 0.0
    for r in rows:
        weight = r["loan_usd"]/total_loan if total_loan else 0
        weighted_ir += float(r["interest_rate"]) * weight

    # simple liquidation LTV heuristic
    liquidation_ltv = min(weighted_ltv * 1.2, 0.95)

    # Monthly EMI from portfolio totals and months

    r_month = weighted_ir / 12.0
    n = months
    P = total_loan
    emi = P * r_month / (1 - (1 + r_month) ** (-n)) if r_month > 0 and n > 0 else 0.0


    return {
        "total_collateral": fmt(total_collateral),
        "total_loan": fmt(total_loan),
        "portfolio_ltv": fmt(weighted_ltv * 100),
        "liquidation_ltv": fmt(liquidation_ltv * 100),
        "interest_rate": fmt(weighted_ir * 100),  # % for the portfolio
        "monthly_emi": fmt(emi),
        "months": n,
    }

