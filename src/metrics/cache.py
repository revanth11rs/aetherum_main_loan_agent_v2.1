# simple ttl cache with dict, no extra deps
import time
from typing import Any, Callable, Tuple

class TTLCache:
    def __init__(self, ttl_seconds: int = 60, max_size: int = 1024):
        self.ttl = ttl_seconds
        self.max = max_size
        self.store: dict[str, Tuple[float, Any]] = {}

    def get(self, key: str):
        now = time.time()
        item = self.store.get(key)
        if not item:
            return None
        ts, val = item
        if now - ts > self.ttl:
            self.store.pop(key, None)
            return None
        return val

    def set(self, key: str, value: Any):
        if len(self.store) >= self.max:
            # dumb eviction: drop one arbitrary item
            self.store.pop(next(iter(self.store)))
        self.store[key] = (time.time(), value)

cache60 = TTLCache(ttl_seconds=60)
