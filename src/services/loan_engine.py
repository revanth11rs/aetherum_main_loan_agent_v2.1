# src/services/loan_engine.py

from typing import List, Dict, Optional
from decimal import Decimal, ROUND_HALF_UP
from ..domain.risk_tiers import tier_info
from ..utils.amortization import amortization_schedule, sum_schedules  # UPDATED

# Base/Federal rate (6.33% as a fraction)
BASE_RATE = 0.0633


def fmt(x: float, places: str = "0.01") -> float:
    """
    Round to given decimal places (as string pattern) using HALF_UP.
    Use str(x) to avoid binary float artifacts.
    """
    return float(Decimal(str(x)).quantize(Decimal(places), rounding=ROUND_HALF_UP))


def _get_pct_change_30d(metrics: Dict) -> Optional[float]:
    """
    Pull 30d % change from metrics with robust key fallback:
      - "pct_change_30d"  (preferred)
      - "pct_change_30"
      - "30dChange(%)"
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
    if ch30 is None:
        return 0.01
    ch30 = abs(ch30)
    if ch30 < 10:
        return 0.01
    if ch30 < 20:
        return 0.015
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
    vol = volatility_premium_from_metrics(metrics)
    total = base + risk + vol

    # keep more decimals for rates; UI will format as %
    return {
        "base_rate": fmt(base, "0.0001"),
        "risk_premium": fmt(risk, "0.0001"),
        "volatility_premium": fmt(vol, "0.0001"),
        "interest_rate": fmt(total, "0.0001"),
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
        "interest_rate": ic["interest_rate"],  # total (fraction)
        # money-ish
        "collateral_usd": fmt(alloc_usd),
        "loan_usd": fmt(loan_amount),
        # helpful for UI: surface the 30d change we used
        "pct_change_30d": _get_pct_change_30d(metrics),
    }


def portfolio_aggregate(rows: List[Dict], months: int) -> Dict:
    """
    Aggregate per-asset rows into portfolio summary.

    NOTE: LTV and interest_rate are returned as PERCENT values (not fractions),
          which matches the Streamlit display.
    """
    total_collateral = sum(r["collateral_usd"] for r in rows)
    total_loan = sum(r["loan_usd"] for r in rows)

    # weighted LTV (fraction)
    weighted_ltv = (total_loan / total_collateral) if total_collateral else 0.0

    # weighted interest by loan share, using the total interest_rate (fraction)
    weighted_ir = 0.0
    for r in rows:
        weight = r["loan_usd"] / total_loan if total_loan else 0.0
        weighted_ir += float(r["interest_rate"]) * weight

    # simple liquidation LTV heuristic (fraction)
    liquidation_ltv = min(weighted_ltv * 1.2, 0.95)

    # margin call LTV (percent): halfway between current and liquidation
    margin_call_pct = ((weighted_ltv * 100.0) + (liquidation_ltv * 100.0)) / 2.0

    # A preliminary EMI using weighted_ir (will be overwritten by schedule-based EMI)
    r_month = weighted_ir / 12.0
    n = int(months)
    P = float(total_loan)
    if n > 0:
        if r_month > 0:
            emi = P * r_month / (1 - (1 + r_month) ** (-n))
        else:
            emi = P / n
    else:
        emi = 0.0

    return {
        "total_collateral": fmt(total_collateral),
        "total_loan": fmt(total_loan),
        "portfolio_ltv": fmt(weighted_ltv * 100),        # percent
        "liquidation_ltv": fmt(liquidation_ltv * 100),   # percent
        "margin_call_ltv": fmt(margin_call_pct),         # percent (NEW)
        "interest_rate": fmt(weighted_ir * 100),         # percent
        "monthly_emi": fmt(emi),                         # placeholder; replaced by attach_amortization()
        "months": n,
    }


# -------------------- Amortization integration --------------------

def attach_amortization(out: Dict) -> Dict:
    """
    Adds:
      out["schedule"] = {
        "portfolio": [ {month, opening_balance, payment, interest, principal, ending_balance}, ... ],
        "assets":    { "BTC": [rows...], "ETH": [rows...] },
        "payments":  { "BTC": 1234.56, ... }   # per-asset level payment (float)
      }
    And sets:
      out["summary"]["monthly_emi"] = sum(per-asset payments)  # SOURCE OF TRUTH
    """
    if not out or "assets" not in out or "summary" not in out:
        return out

    months = int(out["summary"].get("months", 0))
    if months <= 0:
        out["schedule"] = {"portfolio": [], "assets": {}, "payments": {}}
        out["summary"]["monthly_emi"] = 0.0
        return out

    # Per-asset schedules
    per_asset_sched: Dict[str, list] = {}
    per_asset_payment: Dict[str, float] = {}
    for a in out["assets"]:
        sched = amortization_schedule(
            principal_usd=float(a["loan_usd"]),
            annual_rate_frac=float(a["interest_rate"]),  # fraction
            months=months,
        )
        per_asset_sched[a["symbol"]] = sched["schedule"]
        per_asset_payment[a["symbol"]] = float(sched["payment"])

    # Aggregate portfolio schedule
    portfolio_sched = sum_schedules(per_asset_sched)

    # EMI = sum of per-asset level payments (rounded once at end)
    monthly_emi = sum(per_asset_payment.values())
    out["summary"]["monthly_emi"] = fmt(monthly_emi)  # <-- definitive EMI

    out["schedule"] = {
        "portfolio": portfolio_sched,
        "assets": per_asset_sched,
        "payments": per_asset_payment,
    }
    return out
