from typing import Dict, Optional, Tuple
from ..utils.config import settings
from ..utils.http import get
from ..utils.logging import get_logger

log = get_logger(__name__)

def get_metrics(symbol: str) -> Dict:
    """
    Calls your external metrics API:
      GET {METRICS_API_BASE}/metrics/<SYMBOL>
    Expected keys (from your screenshot):
      - volatility_score (required for our model features)
      - pct_change_30d, pct_change_90d, name, symbol, computed_at (optional)
    """
    base = settings.METRICS_API_BASE.rstrip("/")
    url = f"{base}/metrics/{symbol.upper()}"
    
    print(f"Fetching metrics for {symbol} from {url}")
    # Use the utility function to make the GET request
    print("ulalala")
    return get(url)

def get_model_features(symbol: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Returns the two inputs the AI model can use:
      - volatility_score (float)
      - market_cap_usd   (float or None if your metrics API doesn't provide it)
    If market cap isn't present in your /metrics payload, this will be None.
    (The caller can override/provide market cap via `context`.)
    """
    m = get_metrics(symbol)
    vs = _to_float(m.get("volatility_score"))

    # Try a few common keys in case you later add market cap to the payload
    mc = (
        m.get("market_cap") or
        m.get("market_cap_usd") or
        m.get("marketcap") or
        m.get("market_value") or
        m.get("marketValue")
    )
    mc = _to_float(mc)

    if vs is None:
        log.warning(f"metrics for {symbol} missing volatility_score")
    return vs, mc

def _to_float(x) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None

