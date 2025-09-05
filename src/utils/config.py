
import os
from dataclasses import dataclass

@dataclass
class Settings:
    METRICS_API_BASE: str = os.getenv("METRICS_API_BASE", "http://localhost:5002")
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "groq")
    AI_MODEL_NAME: str = os.getenv("AI_MODEL_NAME")
    AI_MODEL_NAME: str = os.getenv("AI_MODEL_NAME", "llama-3.3-70b-versatile")
    AI_MODEL_TEMPERATURE: float = float(os.getenv("AI_MODEL_TEMPERATURE", "0.2"))
    AI_MODEL_MAX_TOKENS: int = int(os.getenv("AI_MODEL_MAX_TOKENS", "2048"))
    AI_MODEL_TOP_P: float = float(os.getenv("AI_MODEL_TOP_P", "0.95"))
    AI_MODEL_FREQUENCY_PENALTY: float = float(os.getenv("AI_MODEL_FREQUENCY_PENALTY", "0.0"))
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    ENV: str = os.getenv("ENV", "dev")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    PORT: int = int(os.getenv("PORT", "5002"))

settings = Settings()
