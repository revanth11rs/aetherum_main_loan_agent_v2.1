
from src.domain.risk_tiers import tier_info

def test_tier_info():
    assert tier_info("Tier 1")["ltv"] == 0.72
