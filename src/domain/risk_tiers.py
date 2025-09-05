# src/domain/risk_tiers.py
from typing import Dict, Any

# One source of truth for LTV and risk premiums (fractions, e.g., 0.015 = 1.5%)
RISK_TIERS = {
    "Tier 1":   {"ltv": 0.72, "risk_premium": 0.05, "note": "Blue-chip, high liquidity"},
    "Tier 1.5": {"ltv": 0.65, "risk_premium": 0.10, "note": "Large-cap, strong liquidity"},
    "Tier 2":   {"ltv": 0.60, "risk_premium": 0.15, "note": "Mid-cap, moderate liquidity"},
    "Tier 3":   {"ltv": 0.55, "risk_premium": 0.25, "note": "High volatility / risk"},
}

def tier_info(tier: str) -> Dict[str, Any]:
    if tier not in RISK_TIERS:
        raise ValueError(f"Unknown risk tier: {tier}")
    return RISK_TIERS[tier]
