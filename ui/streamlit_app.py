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
    """
    x is already a percentage number (e.g., 78.25), not a fraction.
    """
    try:
        return f"{float(x):.{places}f}%"
    except Exception:
        return "—"

def pct_from_fraction(x: float, places: int = 2) -> str:
    """
    x is a fraction (e.g., 0.0825). Convert to percentage text.
    """
    try:
        return f"{float(x) * 100:.{places}f}%"
    except Exception:
        return "—"

# ---- fallback if backend doesn't return schedule ----
def _emi_schedule_fallback(
    total_loan: float,
    annual_rate_percent: float,
    months: int,
    fixed_payment: float | None = None,
):
    """
    Build a portfolio-only EMI schedule using summary fields.
    If fixed_payment is provided, use it as the level payment (to match the text EMI exactly).
    """
    P = float(total_loan or 0.0)
    n = int(months or 0)
    if n <= 0 or P <= 0:
        return []

    r = float(annual_rate_percent or 0.0) / 100.0 / 12.0  # summary interest is in %
    if fixed_payment is not None:
        payment = float(fixed_payment)
    else:
        if r == 0:
            payment = P / n
        else:
            payment = P * r / (1 - (1 + r) ** (-n))

    rows = []
    bal = P
    for m in range(1, n + 1):
        opening = bal
        interest = opening * r
        principal = payment - interest

        # last row fix so ending balance is exactly 0
        if m == n:
            principal = opening
            pay_this = principal + interest
        else:
            pay_this = payment

        bal = max(0.0, opening - principal)
        rows.append({
            "month": m,
            "opening_balance": opening,
            "payment": pay_this,
            "interest": interest,
            "principal": principal,
            "ending_balance": bal,
        })
    return rows

# --------------------- UI ---------------------

st.set_page_config(page_title="Aetherum Loan v2", layout="wide")
st.title("Aetherum AI Loan Calculator — v2")

with st.expander("Connection"):
    st.caption("Backend base URL used by the UI")
    st.code(API_BASE, language="bash")

# -------- Portfolio selector --------
st.subheader("Portfolio Allocation")
symbols = st.multiselect(
    "Select tokens:",
    ["BTC", "ETH", "XRP", "USDT", "SOL", "ADA"],
    default=["BTC", "ETH", "XRP", "USDT"],
)

alloc_total = st.number_input("Total Collateral ($)", 1000, value=1_000_000, step=1000)

# keep per-asset values in session so they survive reruns
if "allocs" not in st.session_state:
    st.session_state.allocs = {}

# remove coins you unselected
for k in list(st.session_state.allocs.keys()):
    if k not in symbols:
        del st.session_state.allocs[k]

# initialize new coins (equal split as a starting point)
init_per = round(alloc_total / max(len(symbols), 1), 2)
for s in symbols:
    st.session_state.allocs.setdefault(s, init_per)

left, right = st.columns([3, 1])

with left:
    st.caption("Enter per-asset allocation (USD)")
    for s in symbols:
        val = st.number_input(
            f"{s} allocation ($)",
            min_value=0.0,
            step=100.0,
            value=float(st.session_state.allocs.get(s, 0.0)),
            key=f"alloc_input_{s}",
        )
        st.session_state.allocs[s] = float(val)

with right:
    if st.button("Distribute equally"):
        eq = round(alloc_total / max(len(symbols), 1), 2)
        for s in symbols:
            st.session_state.allocs[s] = eq

# diff banner
entered_sum = sum(st.session_state.allocs.get(s, 0.0) for s in symbols)
diff = round(alloc_total - entered_sum, 2)

if symbols:
    if abs(diff) < 0.01:
        st.success(f"All collateral assigned ✅ Total = {fmt_usd(entered_sum)}")
    elif diff > 0:
        st.info(f"{fmt_usd(diff)} unassigned")
    else:
        st.error(f"Over-assigned by {fmt_usd(-diff)}")

cols = st.columns(2)
with cols[0]:
    if st.button("Preview Metrics (first symbol)") and symbols:
        s0 = symbols[0]
        try:
            data = requests.get(f"{API_BASE}/metrics/{s0}", timeout=10).json()
            st.json(data)
        except Exception as e:
            st.error(str(e))

# -------- Loan input --------
st.subheader("Loan Input")
months = st.selectbox("Length of loan (months)", [3, 6, 9, 12], index=1)
payout = st.selectbox("Payout currency", ["USDC", "USDT", "USD"])
bank = st.selectbox("Select bank", ["American Bank", "Silvergate", "Signature"])

calc = st.button("Calculate Loan")

# --------------------- Calculate ---------------------
if calc and symbols:
    assets = [{"symbol": s, "allocation_usd": float(st.session_state.allocs.get(s, 0.0))} for s in symbols]

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
            st.title("Aetherum Loan")
            try:
                sresp = requests.post(f"{API_BASE}/loan/summary", json={"calculation": out}, timeout=60)
                sdata = sresp.json()
                st.subheader("Analyst Summary")
                if sresp.status_code == 200 and "markdown" in sdata:
                    st.markdown(sdata["markdown"])
                    st.download_button(
                        "Download Summary (.md)",
                        data=sdata["markdown"],
                        file_name="analyst_summary.md",
                        mime="text/markdown",
                    )
                else:
                    st.info("Summary unavailable")
            except Exception as e:
                st.warning(f"Summary error: {e}")

            st.markdown("**Asset-Based Loan Breakdown**")

            df = pd.DataFrame(out["assets"])
            if "pct_change_24h" not in df.columns:
                df["pct_change_24h"] = None

            table = pd.DataFrame({
                "Asset": df["symbol"],
                "Risk Tier": df["tier"],
                "LTV (%)": (df["ltv"] * 100).apply(lambda x: f"{x:.0f}%"),
                "Base Rate (%)": df["base_rate"].apply(pct_from_fraction),
                "Risk Premium (%)": df["risk_premium"].apply(pct_from_fraction),
                "Vol Premium (%)": df["volatility_premium"].apply(pct_from_fraction),
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
            # NEW: margin call LTV
            if "margin_call_ltv" in s:
                st.write(f"**Margin Call LTV:** {fmt_pct(s['margin_call_ltv'])}")
            st.write(f"**Interest Rate:** {fmt_pct(s['interest_rate'])}")
            st.write(f"**Loan Duration:** {s['months']} months")
            # NOTE: summary.monthly_emi now equals sum of per-asset payments
            st.write(f"**Monthly Repayment (EMI):** {fmt_usd(s['monthly_emi'])}")

            # ---------- Amortization ----------
            server_sched = (out.get("schedule") or {})
            portfolio_rows = server_sched.get("portfolio") or []

            # If server didn't send schedule, build a portfolio-only fallback
            if not portfolio_rows:
                portfolio_rows = _emi_schedule_fallback(
                    total_loan=s.get("total_loan", 0.0),
                    annual_rate_percent=s.get("interest_rate", 0.0),  # percent
                    months=s.get("months", 0),
                    fixed_payment=s.get("monthly_emi", None),         # ensure text == table
                )

            st.subheader("Amortization Schedule")

            if portfolio_rows:
                p = pd.DataFrame(portfolio_rows).astype({
                    "opening_balance": "float",
                    "payment": "float",
                    "interest": "float",
                    "principal": "float",
                    "ending_balance": "float",
                })

                display = pd.DataFrame({
                    "Month": p["month"],
                    "Opening ($)": p["opening_balance"].apply(fmt_usd),
                    "Payment ($)": p["payment"].apply(fmt_usd),
                    "Interest ($)": p["interest"].apply(fmt_usd),
                    "Principal ($)": p["principal"].apply(fmt_usd),
                    "Ending ($)": p["ending_balance"].apply(fmt_usd),
                })

                tabs = st.tabs(["Portfolio"])
                with tabs[0]:
                    st.dataframe(display, use_container_width=True)
                    st.download_button(
                        "Download Portfolio Amortization (CSV)",
                        data=p.to_csv(index=False),
                        file_name="amortization_portfolio.csv",
                        mime="text/csv",
                    )
                    try:
                        st.line_chart(
                            p.set_index("month")[["opening_balance", "ending_balance"]],
                            height=240,
                        )
                    except Exception:
                        pass
            else:
                st.info("No amortization schedule available")

            # --------- NEW: Analyst Summary (backend-generated) ---------
            
    except Exception as e:
        st.error(str(e))
elif calc and not symbols:
    st.warning("pick at least one token 🙏")
