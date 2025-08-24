# Aetherum v2

Production-ready rewrite of the crypto-backed loan calculator with:
- Flask API backend
- Streamlit front-end
- External volatility metrics API client (no in-house calc)
- Pluggable AI model for **risk tier** assignment (default via Groq, easily swappable)
- Separate module for **risk tiers and interest mapping**
- Structured logging + centralized error handling
- .env-driven config

## Quickstart

```bash
# 1) Python 3.10+ recommended
python -m venv .venv && source .venv/bin/activate

# 2) Install deps
pip install -r requirements.txt

# 3) Copy .env.example to .env and fill values
cp .env.example .env

# 4) Run backend (Flask)
export FLASK_APP=src/app.py
flask run --port 5002

# 5) Run UI (Streamlit)
streamlit run ui/streamlit_app.py
```

## ENV
See `.env.example` for all variables.


## Project Layout

```
aetherum_v2/
├─ src/
│  ├─ app.py                 # Flask app factory + routes
│  ├─ api/
│  │  ├─ routes.py           # Blueprint with endpoints
│  │  └─ schemas.py          # Pydantic-style validation (dataclasses here)
│  ├─ services/
│  │  ├─ volatility_client.py # Calls your existing /metrics/<symbol> API
│  │  ├─ model_client.py     # AI client abstraction (default Groq)
│  │  └─ loan_engine.py      # Core loan calculation logic
│  ├─ domain/
│  │  ├─ risk_tiers.py       # Tiers + interest mapping + helper funcs
│  │  └─ errors.py           # Custom exceptions
│  ├─ utils/
│  │  ├─ config.py           # Env config
│  │  ├─ logging.py          # Structured logger
│  │  └─ http.py             # Simple HTTP wrapper with retries
│  └─ __init__.py
├─ ui/
│  └─ streamlit_app.py       # Streamlit front-end
├─ tests/
│  ├─ test_risk_tiers.py
│  └─ test_loan_engine.py
├─ requirements.txt
├─ .env.example
└─ README.md
```

## API (v1)

- `GET /health` → ok
- `GET /metrics/<symbol>` → proxy to external metrics API (optional)
- `POST /risk-tier` → body: `{"symbol":"BTC","context":{...}}` → `{"symbol":"BTC","tier":"Tier 1.5","score":0.82}`
- `POST /loan/calculate` → portfolio + loan params → breakdown + totals

