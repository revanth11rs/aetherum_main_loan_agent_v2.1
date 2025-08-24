# src/services/model_client.py

from typing import Dict, Tuple, Optional
from ..utils.config import settings
from ..utils.logging import get_logger

log = get_logger(__name__)

class ModelClient:
    """
    Risk tier is decided ONLY from:
      1) volatility_score  (we fetch from your /metrics/<symbol>)
      2) the asset's market value / market cap (decided by the AI model itself; we do NOT fetch it)
    """
    def __init__(self):
        self.provider = settings.AI_PROVIDER

    def risk_tier(self, symbol: str, context: Dict) -> Tuple[str, float]:
        if self.provider == "groq":
            return self._groq_risk_tier(symbol, context)
        raise ValueError(f"Unsupported AI_PROVIDER: {self.provider}")

    # ----------------- helpers -----------------

    def _get_volatility(self, symbol: str, context: Dict) -> Optional[float]:
        """
        Pull volatility_score from the external metrics API first.
        If that fails, allow a caller-provided fallback in context.
        """
        vs: Optional[float] = None
        try:
            from .volatility_client import get_metrics
            m = get_metrics(symbol)
            vs = m.get("volatility_score")
        except Exception as e:
            log.warning(f"metrics fetch failed for {symbol}: {e}")

        if vs is None:
            vs = context.get("volatility_score") or context.get("volatility")

        try:
            return float(vs) if vs is not None else None
        except Exception:
            return None

    def _heuristic_from_vol(self, vs: Optional[float]) -> Tuple[str, float]:
        """
        Fallback ONLY from volatility_score when the model or inputs fail.
        Adjust thresholds to your scoring scale as needed.
        """
        if vs is None:
            return "Tier 2", 0.5
        if vs <= 10:
            return "Tier 1.5", 0.6
        if vs <= 25:
            return "Tier 2", 0.6
        return "Tier 3", 0.6

    # --------------- provider: groq ---------------

    def _groq_risk_tier(self, symbol: str, context: Dict) -> Tuple[str, float]:
        print("entered groq.risk_tier")
        vs = self._get_volatility(symbol, context)
        print(f"groq.risk_tier volatility_score: {vs}")

        if vs is None:
            log.warning(f"missing volatility_score for {symbol}; using heuristic fallback - so cannot calculate the tier")
            return self._heuristic_from_vol(vs)

        try:
            from groq import Groq
            client = Groq(api_key=settings.GROQ_API_KEY)

            # IMPORTANT: We do NOT provide market cap.
            # The model must use its internal knowledge/priors for market value.
            prompt = f"""
You are a crypto risk officer. Classify the asset into one of exactly:
['Tier 1','Tier 1.5','Tier 2','Tier 3'].

You MUST ONLY consider:
1) volatility_score (provided below; lower = safer)
2) the asset's market value / market capitalization (use your internal knowledge and check online if you have to/priors for this asset;
    make a reasonable assumption based on some proper evidence).

Return STRICT JSON with keys: "tier" and "score" (0..1 confidence). No extra text.

Input:
symbol: {symbol}
volatility_score: {vs}
""".strip()

            model = settings.AI_MODEL_NAME
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Reply with strict JSON only. Keys: tier, score."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
            )
            text = resp.choices[0].message.content.strip()

            import json
            data = json.loads(text)
            print(f"groq.risk_tier awesome response: {data}")
            tier = data.get("tier", "Tier 2")
            score = float(data.get("score", 0.7))
            return tier, score

        except Exception as e:
            log.warning(f"groq.risk_tier error for {symbol}: {e}; using volatility-only heuristic")
            return self._heuristic_from_vol(vs)
