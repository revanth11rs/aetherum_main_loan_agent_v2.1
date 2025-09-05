
from src.services.loan_engine import per_asset_breakdown, portfolio_aggregate

def test_breakdown_and_aggregate():
    rows = []
    rows.append({**per_asset_breakdown(250000, "Tier 1"), "symbol":"BTC"})
    rows.append({**per_asset_breakdown(250000, "Tier 1.5"), "symbol":"ETH"})
    rows.append({**per_asset_breakdown(250000, "Tier 1"), "symbol":"XRP"})
    rows.append({**per_asset_breakdown(250000, "Tier 1"), "symbol":"USDT"})
    agg = portfolio_aggregate(rows)
    assert agg["total_collateral"] == 1000000.0
    assert agg["total_loan"] > 0
