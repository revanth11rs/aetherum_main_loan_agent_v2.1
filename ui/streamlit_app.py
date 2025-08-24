# ui/streamlit_app.py

import os
import json
import requests
import pandas as pd
import streamlit as st

# You can override this when launching:
#   API_BASE=http://localhost:5002 streamlit run ui/streamlit_app.py
API_BASE = os.getenv("API_BASE", "http://localhost:5002")

# --------------------- helpers ---------------------

def fmt_usd(x: float) -> str:
    try:
        return f"${float(x):,.2f}"
    except Exception:
        return "$0.00"

def fmt_pct(x: float, places: int = 2) -> str:
    try:
        return f"{float(x):.{places}f}%"
    except Exception:
        return "—"

def pct_from_fraction(x: float, places: int = 2) -> str:
    try:
        return f"{float(x) * 100:.{places}f}%"
    except Exception:
        return "—"

# --------------------- UI ---------------------

st.set_page_config(page_title="Aetherum Loan v2", layout="wide")
st.title("Aetherum AI Loan Calculator — v2")

with st.expander("Connection"):
    st.caption("Backend base URL used by the UI")
    st.code(API_BASE, language="bash")

# Portfolio selector
st.subheader("Portfolio Allocation")
symbols = st.multiselect(
    "Select tokens:",
    ["BTC", "ETH", "XRP", "USDT", "SOL", "ADA"],
    default=["BTC", "ETH", "XRP", "USDT"],
)

alloc_total = st.number_input("Total Collateral ($)", 1000, value=1_000_000, step=1000)
per = round(alloc_total / len(symbols), 2) if symbols else 0.0
st.write("Per-asset allocation:", fmt_usd(per))

cols = st.columns(2)

with cols[0]:
    if st.button("Preview Metrics (first symbol)") and symbols:
        s = symbols[0]
        try:
            data = requests.get(f"{API_BASE}/metrics/{s}", timeout=10).json()
            st.json(data)
        except Exception as e:
            st.error(str(e))

st.subheader("Loan Input")
months = st.selectbox("Length of loan (months)", [3, 6, 9, 12], index=1)
payout = st.selectbox("Payout currency", ["USDC", "USDT", "USD"])
bank = st.selectbox("Select bank", ["American Bank", "Silvergate", "Signature"])

calc = st.button("Calculate Loan")

# --------------------- Calculate ---------------------

if calc and symbols:
    assets = [{"symbol": s, "allocation_usd": per} for s in symbols]
    try:
        resp = requests.post(
            f"{API_BASE}/loan/calculate",
            json={
                "assets": assets,
                "months": months,
                "payout_currency": payout,
                "bank": bank,
            },
            timeout=30,
        )
        out = resp.json()

        if resp.status_code != 200:
            st.error(out)
        else:
            # Save/download full JSON profile
            st.download_button(
                "Download JSON Profile",
                data=json.dumps(out, indent=2),
                file_name="loan_profile.json",
                mime="application/json",
            )

            # ---------- Asset table ----------
            st.subheader("Aetherum Loan")
            st.markdown("**Asset-Based Loan Breakdown**")

            df = pd.DataFrame(out["assets"])

            # Fill missing for display
            if "pct_change_24h" not in df.columns:
                df["pct_change_24h"] = None

            table = pd.DataFrame({
                "Asset": df["symbol"],
                "Risk Tier": df["tier"],
                # "24h Vol (%)": df["pct_change_24h"].fillna("—").apply(lambda x: "—" if x == "—" else fmt_pct(x)),
                "LTV (%)": (df["ltv"] * 100).apply(lambda x: f"{x:.0f}%"),
                # Interest components (fractions → %)
                "Base Rate (%)": df["base_rate"].apply(pct_from_fraction),
                "Risk Premium (%)": df["risk_premium"].apply(pct_from_fraction),
                "Vol Premium (%)": df["volatility_premium"].apply(pct_from_fraction),
                # Total interest (already the sum returned by backend)
                "Interest Rate (%)": df["interest_rate"].apply(pct_from_fraction),
                "Collateral ($)": df["collateral_usd"].apply(fmt_usd),
                "Loan Amount ($)": df["loan_usd"].apply(fmt_usd),
            })

            st.dataframe(table, use_container_width=True)

            # ---------- Final loan details ----------
            s = out["summary"]
            st.subheader("Final Loan Details")
            st.write(f"**Total Collateral Selected:** {fmt_usd(s['total_collateral'])}")
            st.write(f"**Total Loan Amount:** {fmt_usd(s['total_loan'])}")
            st.write(f"**Portfolio LTV:** {fmt_pct(s['portfolio_ltv'])}")
            st.write(f"**Liquidation LTV:** {fmt_pct(s['liquidation_ltv'])}")
            st.write(f"**Interest Rate:** {fmt_pct(s['interest_rate'])}")
            st.write(f"**Loan Duration:** {s['months']} months")
            st.write(f"**Monthly Repayment (EMI):** {fmt_usd(s['monthly_emi'])}")
            


    except Exception as e:
        st.error(str(e))
elif calc and not symbols:
    st.warning("pick at least one token 🙏")
