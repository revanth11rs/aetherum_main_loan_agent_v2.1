import os
from typing import Optional, Dict, Any
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGODB_URI")
_client = MongoClient(MONGO_URI) if MONGO_URI else None
_db = _client.get_default_database() if _client else None
_collection = _db["loan_agent_metrics"] if _db is not None else None   # <-- fixed

def get_latest_metrics(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Returns the most recent doc for the symbol, or None.
    Expected doc shape:
      {
        symbol, name, "30dChange(%)", "90dChange(%)",
        volatility_score, computed_at (datetime)
      }
    """
    if _collection is None:
        return None

    cur = (
        _collection
        .find({"symbol": symbol})
        .sort("computed_at", -1)
        .limit(1)
    )
    return next(cur, None)
