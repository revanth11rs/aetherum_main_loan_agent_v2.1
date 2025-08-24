from typing import List
from pycoingecko import CoinGeckoAPI

cg = CoinGeckoAPI()

def fetch_historical_prices(id: str, days: int) -> List[float]:
    data = cg.get_coin_market_chart_by_id(
        id=id, vs_currency="usd", days=days, interval="daily"
    )["prices"]
    return [p[1] for p in data]

def fetch_pct_change(id: str, days: int) -> float:
    prices = fetch_historical_prices(id, days)
    start, end = prices[0], prices[-1]
    return (end - start) / start * 100.0
