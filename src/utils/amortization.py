# src/utils/amortization.py

from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List

Money = float


def _q2(x: float) -> float:
    """Round to cents using HALF_UP (banker's-friendly)."""
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def amortization_schedule(
    principal_usd: Money,
    annual_rate_frac: float,
    months: int,
) -> Dict:
    """
    Build a standard level-payment amortization schedule.

    Returns:
      {
        "payment": <float>,                     # monthly level payment (cents-rounded)
        "schedule": [                           # one row per month
          { "month": 1, "opening_balance": ..,
            "payment": .., "interest": ..,
            "principal": .., "ending_balance": .. },
          ...
        ]
      }
    """
    P = float(principal_usd or 0.0)
    n = int(months or 0)
    r_m = float(annual_rate_frac or 0.0) / 12.0

    if n <= 0 or P <= 0:
        return {"payment": 0.0, "schedule": []}

    if r_m == 0.0:
        payment = P / n
    else:
        payment = P * r_m / (1.0 - (1.0 + r_m) ** (-n))

    # round the level payment to cents once and stick to it
    payment = _q2(payment)

    rows: List[Dict] = []
    bal = P
    for m in range(1, n + 1):
        opening = bal
        interest = _q2(opening * r_m)
        principal = _q2(payment - interest)

        # final row fix so balance hits exactly zero
        if m == n:
            principal = _q2(opening)
            pay_this = _q2(principal + interest)
        else:
            pay_this = payment

        bal = _q2(opening - principal)
        rows.append(
            {
                "month": m,
                "opening_balance": _q2(opening),
                "payment": _q2(pay_this),
                "interest": _q2(interest),
                "principal": _q2(principal),
                "ending_balance": _q2(bal),
            }
        )

    return {"payment": payment, "schedule": rows}


def sum_schedules(per_asset: Dict[str, List[Dict]]) -> List[Dict]:
    """
    Pointwise-sum multiple schedules (assumes equal length).
    """
    if not per_asset:
        return []

    # length check (take the first asset as reference)
    any_key = next(iter(per_asset))
    ref = per_asset[any_key]
    n = len(ref)

    agg: List[Dict] = []
    for i in range(n):
        opening = interest = principal = payment = ending = 0.0
        month = ref[i]["month"]
        for sch in per_asset.values():
            row = sch[i]
            opening += float(row["opening_balance"])
            interest += float(row["interest"])
            principal += float(row["principal"])
            payment += float(row["payment"])
            ending += float(row["ending_balance"])

        agg.append(
            {
                "month": month,
                "opening_balance": _q2(opening),
                "payment": _q2(payment),
                "interest": _q2(interest),
                "principal": _q2(principal),
                "ending_balance": _q2(ending),
            }
        )
    return agg
