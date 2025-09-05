
import logging
import json
from datetime import datetime

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.getLevelName(_getenv('LOG_LEVEL', 'INFO')))
    handler = logging.StreamHandler()
    formatter = JsonFormatter()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

def _getenv(key, default=None):
    import os
    return os.getenv(key, default)

class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "name": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)
