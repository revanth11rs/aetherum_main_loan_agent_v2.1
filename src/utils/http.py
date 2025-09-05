
import time
import requests
from .logging import get_logger

log = get_logger(__name__)

def  get(url, timeout=10, retries=2):
    for attempt in range(retries+1):
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            log.warning(f"http.get failed attempt={attempt} url={url} err={e}")
            if attempt == retries:
                raise
            time.sleep(0.5 * (attempt+1))
