# src/services/summary_service.py

from __future__ import annotations
import json
import statistics
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
import os
import requests
import xml.etree.ElementTree as ET

# ------------------------------ config ------------------------------

# LLM (optional)
USE_LLM_SUMMARY = os.getenv("USE_LLM_SUMMARY", "false").lower() in {"1", "true", "yes"}
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
AI_MODEL_NAME = os.getenv("AI_MODEL_NAME", "llama-3.3-70b-versatile")
AI_TEMPERATURE = float(os.getenv("AI_MODEL_TEMPERATURE", "0.2"))
AI_MAX_TOKENS = int(os.getenv("AI_MODEL_MAX_TOKENS", "800"))
AI_TOP_P = float(os.getenv("AI_MODEL_TOP_P", "0.95"))
AI_FREQ_PENALTY = float(os.getenv("AI_MODEL_FREQUENCY_PENALTY", "0.0"))

# Smart-contract (optional)
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "").strip()
EXPLORER_BASE_URL = os.getenv("EXPLORER_BASE_URL", "").rstrip("/")  # e.g., https://etherscan.io/address
CHAIN_NAME = os.getenv("CHAIN_NAME", "Ethereum")

# News
NEWS_PER_COIN = int(os.getenv("NEWS_PER_COIN", "3"))
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "10"))

# Symbol -> (coingecko_id, human_name)
COIN_MAP: Dict[str, Tuple[str, str]] = {
    "BTC": ("bitcoin", "Bitcoin"),
    "ETH": ("ethereum", "Ethereum"),
    "XRP": ("ripple", "XRP"),
    "USDT": ("tether", "Tether"),
    "SOL": ("solana", "Solana"),
    "ADA": ("cardano", "Cardano"),
}

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
HEADERS_JSON = {"Accept": "application/json"}


# ------------------------------ time & formatting ------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _fmt_pct(x: Optional[float]) -> str:
    try:
        return f"{float(x):.2f}%"
    except Exception:
        return "—"


def _fmt_usd(x: Optional[float]) -> str:
    try:
        return f"${float(x):,.2f}"
    except Exception:
        return "$0.00"


# ------------------------------ data fetchers ------------------------------

def _cg_market_chart(coin_id: str, days: int = 35) -> Optional[List[Tuple[int, float]]]:
    """
    Fetch daily USD prices for the last `days` via CoinGecko.
    Returns a list of (timestamp_ms, price).
    """
    url = f"{COINGECKO_BASE}/coins/{coin_id}/market_chart"
    params = {"vs_currency": "usd", "days": str(days), "interval": "daily"}
    try:
        r = requests.get(url, params=params, headers=HEADERS_JSON, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        return [(int(p[0]), float(p[1])) for p in data.get("prices", [])]
    except Exception:
        return None


def _pct_change_over_window(prices: List[Tuple[int, float]], lookback_days: int) -> Optional[float]:
    """
    Simple % change: (latest / price_n_days_ago - 1) * 100
    Assumes one price per day (daily interval).
    """
    if not prices or len(prices) < lookback_days + 1:
        return None
    last_price = prices[-1][1]
    past_price = prices[-(lookback_days + 1)][1]
    if past_price == 0:
        return None
    return (last_price / past_price - 1.0) * 100.0


def _realized_vol_30d(prices: List[Tuple[int, float]]) -> Optional[float]:
    """
    30d realized volatility as stdev of daily simple returns, expressed in % (not annualized).
    """
    if not prices or len(prices) < 2:
        return None
    window = prices[-31:] if len(prices) >= 31 else prices
    rets = []
    for i in range(1, len(window)):
        p0 = window[i - 1][1]
        p1 = window[i][1]
        if p0 > 0:
            rets.append((p1 / p0) - 1.0)
    if len(rets) < 2:
        return None
    try:
        return statistics.pstdev(rets) * 100.0
    except Exception:
        return None


# ------------------------------ news fetchers ------------------------------

def _fetch_rss(url: str) -> List[Dict[str, Any]]:
    """
    Fetch and parse an RSS feed. Returns list of dicts with title, link, published (string).
    """
    items: List[Dict[str, Any]] = []
    try:
        resp = requests.get(url, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub = (item.findtext("pubDate") or "").strip()
            items.append({"title": title, "link": link, "published": pub})
    except Exception:
        pass
    return items


def _recent_coin_headlines(coin_human_name: str) -> List[Dict[str, str]]:
    """
    Pull a few recent headlines mentioning the coin name from CoinDesk + CoinTelegraph RSS.
    Heuristic filter: title contains coin name (case-insensitive).
    """
    feeds = [
        "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml",
        "https://cointelegraph.com/rss",
    ]
    headlines: List[Dict[str, str]] = []
    target = coin_human_name.lower()

    for feed in feeds:
        for item in _fetch_rss(feed):
            title = item["title"]
            if target in title.lower():
                headlines.append(
                    {"title": title, "link": item["link"], "published": item["published"]}
                )
    return headlines[:NEWS_PER_COIN]


# ------------------------------ enrichment ------------------------------

def _enrich_coin(symbol: str) -> Dict[str, Any]:
    """
    For a symbol (e.g., 'BTC'), fetch 5d/10d/30d changes, realized vol, and recent headlines.
    """
    coin_id, coin_name = COIN_MAP.get(symbol, (None, None))
    result = {
        "symbol": symbol,
        "coin_name": coin_name or symbol,
        "pct_5d": None,
        "pct_10d": None,
        "pct_30d": None,
        "realized_vol_30d": None,
        "headlines": [],  # list of {title, link, published}
    }
    if not coin_id:
        return result

    prices = _cg_market_chart(coin_id, days=35) or []
    if prices:
        result["pct_5d"] = _pct_change_over_window(prices, 5)
        result["pct_10d"] = _pct_change_over_window(prices, 10)
        result["pct_30d"] = _pct_change_over_window(prices, 30)
        result["realized_vol_30d"] = _realized_vol_30d(prices)

    try:
        result["headlines"] = _recent_coin_headlines(coin_name or symbol)
    except Exception:
        result["headlines"] = []

    return result


def _enrich_portfolio(calc_out: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build an enrichment block keyed by symbol with perf & news.
    """
    assets = calc_out.get("assets", [])
    symbols = [a.get("symbol") for a in assets if a.get("symbol")]
    unique_symbols: List[str] = []
    for s in symbols:
        if s not in unique_symbols:
            unique_symbols.append(s)

    return {sym: _enrich_coin(sym) for sym in unique_symbols}


# ------------------------------ deterministic report ------------------------------

def _build_report_markdown(calc_out: Dict[str, Any], enrich: Dict[str, Any]) -> str:
    """
    Build markdown with sections:
      - Market snapshot
      - Collateral coins (5d/10d/30d + headlines + volatility)
      - LTV overview
      - Portfolio interest rate
      - Smart contract terms
    """
    s = calc_out.get("summary", {})
    assets = calc_out.get("assets", [])

    # Market Snapshot
    up_5 = up_10 = up_30 = 0
    total = len(enrich)
    for _, info in enrich.items():
        if info.get("pct_5d") is not None and info["pct_5d"] >= 0:
            up_5 += 1
        if info.get("pct_10d") is not None and info["pct_10d"] >= 0:
            up_10 += 1
        if info.get("pct_30d") is not None and info["pct_30d"] >= 0:
            up_30 += 1

    snapshot_lines = [
        f"- Coins up over **5d**: {up_5}/{total}",
        f"- Coins up over **10d**: {up_10}/{total}",
        f"- Coins up over **30d**: {up_30}/{total}",
        f"- Portfolio term: **{int(s.get('months') or 0)} months**",
    ]

    # Per-coin section
    coin_sections: List[str] = []
    for a in assets:
        sym = a.get("symbol")
        info = enrich.get(sym, {})
        name = info.get("coin_name", sym)
        p5 = _fmt_pct(info.get("pct_5d"))
        p10 = _fmt_pct(info.get("pct_10d"))
        p30 = _fmt_pct(info.get("pct_30d"))
        vol = info.get("realized_vol_30d")
        vol_txt = _fmt_pct(vol)

        if vol is None:
            risk_line = "- Risk/volatility: data limited; keep conservative LTV discipline"
        elif vol < 5:
            risk_line = "- Risk/volatility: **low** (30-day realized vol under 5%)"
        elif vol < 15:
            risk_line = "- Risk/volatility: **moderate** (30-day realized vol 5–15%)"
        else:
            risk_line = "- Risk/volatility: **elevated** (30-day realized vol above 15%)"

        headlines = info.get("headlines", [])[:NEWS_PER_COIN]
        if headlines:
            news_lines = ["- Recent headlines:"]
            for h in headlines:
                ttl = h.get("title", "").strip()
                link = h.get("link", "").strip()
                pub = h.get("published", "").strip()
                news_lines.append(f"  - [{ttl}]({link}) — _{pub}_")
        else:
            news_lines = ["- Recent headlines: (none found in the last few days)"]

        coin_md = "\n".join(
            [
                f"**{name} ({sym})**",
                f"- 5d: {p5} | 10d: {p10} | 30d: {p30}",
                f"- 30-day realized volatility: {vol_txt}",
                risk_line,
                *news_lines,
            ]
        )
        coin_sections.append(coin_md)

    # LTV overview
    ltv_lines = [
        f"- **Portfolio LTV (current)**: {_fmt_pct(s.get('portfolio_ltv'))} — share of loan vs. collateral now.",
        f"- **Margin Call LTV**: {_fmt_pct(s.get('margin_call_ltv'))} — checkpoint to top up collateral or reduce exposure.",
        f"- **Liquidation LTV**: {_fmt_pct(s.get('liquidation_ltv'))} — threshold where positions may be closed to repay the loan.",
    ]

    # Interest rate overview
    ir_lines = [
        f"- **Portfolio interest rate**: {_fmt_pct(s.get('interest_rate'))}.",
        f"- **Monthly EMI**: {_fmt_usd(s.get('monthly_emi'))} for {int(s.get('months') or 0)} months.",
    ]

    # Smart contract terms
    sc_lines = [
        "- **Term**: 6-month loan.",
        "- **Custody**: Selected collateral coins move from the borrower’s specified wallet(s) to Aetherum’s custody smart contract for the duration of the loan.",
        "- **Withdrawal/repayment**: Coins are released back after full repayment; early repayment allowed per contract terms.",
    ]
    if CONTRACT_ADDRESS and EXPLORER_BASE_URL:
        sc_lines.append(f"- **Contract** ({CHAIN_NAME}): [`{CONTRACT_ADDRESS}`]({EXPLORER_BASE_URL}/{CONTRACT_ADDRESS})")
    elif CONTRACT_ADDRESS:
        sc_lines.append(f"- **Contract** ({CHAIN_NAME}): `{CONTRACT_ADDRESS}` (paste into your preferred block explorer)")

    # assemble markdown (avoid splatting a conditional)
    md_sections: List[str] = []
    md_sections += ["## Market snapshot", *snapshot_lines, ""]
    md_sections += ["## Collateral coins — performance & risk"]
    if coin_sections:
        md_sections += [sec + "\n" for sec in coin_sections]
    else:
        md_sections += ["(no assets provided)"]
    md_sections += ["", "## LTV overview", *ltv_lines, ""]
    md_sections += ["## Portfolio interest rate", *ir_lines, ""]
    md_sections += ["## Smart contract terms", *sc_lines]

    return "\n".join(md_sections).strip()


# ------------------------------ optional LLM wrapper ------------------------------

def _groq_chat(system: str, user: str) -> str:
    """
    Optional rewrite via Groq to adjust tone only. We keep content grounded by
    passing the already-built markdown as the content (no new numbers).
    """
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set")

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": AI_MODEL_NAME,
        "temperature": AI_TEMPERATURE,
        "max_tokens": AI_MAX_TOKENS,
        "top_p": AI_TOP_P,
        "frequency_penalty": AI_FREQ_PENALTY,
        "messages": [
            {"role": "system", "content": "You are a concise financial analyst. Keep the structure and numbers exactly as given. Improve clarity only."},
            {"role": "user", "content": "Rewrite the following markdown for clarity and flow without changing any numbers or headings:"},
            {"role": "user", "content": user},
        ],
    }
    r = requests.post(url, headers=headers, json=payload, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"].strip()


# ------------------------------ public entry point ------------------------------

def build_analyst_summary(calc_out: Dict[str, Any]) -> Dict[str, Any]:
    """
    Entry point used by /loan/summary.

    Input: the JSON you already return from /loan/calculate (must include 'summary' and 'assets').
    Output:
      {
        "markdown": "<report>",
        "provider": "deterministic" | "groq",
        "model": "<name or 'none'>",
        "used_llm": bool
      }
    """
    enriched = _enrich_portfolio(calc_out)
    md = _build_report_markdown(calc_out, enriched)

    if USE_LLM_SUMMARY:
        try:
            md_llm = _groq_chat(system="keep headings & numbers unchanged", user=md)
            return {"markdown": md_llm, "provider": "groq", "model": AI_MODEL_NAME, "used_llm": True}
        except Exception:
            pass  # fall back to deterministic

    return {"markdown": md, "provider": "deterministic", "model": "none", "used_llm": False}
