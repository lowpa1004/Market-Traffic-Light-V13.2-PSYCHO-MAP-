import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="투자 신호등 V13 CORE", layout="wide")
st.title("🚦 투자 신호등 V13 CORE")

RISK_MULTIPLIER = {
    "SOXL": 1.5, "TQQQ": 1.3, "TECL": 1.3, "SPXL": 1.2,
    "QQQ": 1.0, "SPY": 1.0, "SCHD": 0.8, "BRK-B": 0.8
}

tickers = {
    "주력": ["QQQ", "TQQQ", "SOXL", "SCHD"],
    "전략": ["NVDA", "TSLA", "AAPL", "MSFT", "AMD", "SMH", "QLD"]
}
all_tickers = tickers["주력"] + tickers["전략"]

@st.cache_data(ttl=3600)
def load_data(symbol, years=10):
    start = datetime.now() - timedelta(days=int(years * 365.25))
    df = yf.download(symbol, start=start, progress=False, auto_adjust=True)
    if df is None or df.empty or len(df) < 200:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df[['Close']].dropna()

def signal(mdd, mom, disp, vix):
    if mdd <= -0.30 or disp <= -0.15:
        sig = 3.0
    elif mdd <= -0.10 or mom <= -0.10:
        sig = 2.0
    elif mom >= 0.10 and disp >= 0.20:
        sig = 0.3
    elif mom >= 0.05:
        sig = 0.7
    else:
        sig = 1.0

    if vix >= 35:
        sig = max(sig, 2.5)
    elif vix <= 13:
        sig = min(sig, 0.6)

    return sig

def exec_power(sig, risk):
    return min(np.log1p(sig * risk) * 1.6, 2.3)

def status(sig):
    if sig >= 2:
        return "LOW (BUY ZONE)", "#004d1a"
    elif sig <= 0.7:
        return "OVERHEATED (CAUTION)", "#800000"
    return "NORMAL", "#333333"

with st.sidebar:
    years = st.slider("Years", 3, 15, 10)
    budget = st.number_input("Monthly Budget", 100)

vix = load_data("^VIX", years)
vix_now = vix['Close'].iloc[-1] if vix is not None else 20

tab1, tab2 = st.tabs(["Signals", "Backtest"])

with tab1:
    st.subheader(f"VIX: {vix_now:.2f}")

    cols = st.columns(4)

    for i, t in enumerate(all_tickers):
        df = load_data(t, 2)
        if df is None:
            continue

        p = df['Close'].iloc[-1]
        ath = df['Close'].cummax().iloc[-1]
        sma = df['Close'].rolling(200).mean().iloc[-1]

        mdd = (p - ath) / ath
        mom = (p - df['Close'].iloc[-22]) / df['Close'].iloc[-22]
        disp = (p - sma) / sma

        sig = signal(mdd, mom, disp, vix_now)
        power = exec_power(sig, RISK_MULTIPLIER.get(t, 1.0))
        txt, color = status(sig)

        with cols[i % 4]:
            st.markdown(
                f"""
                <div style="background:{color}; padding:12px; border-radius:10px; color:white;">
                <b>{t}</b><br>
                {txt}<br>
                <h2>{power:.2f}x</h2>
                </div>
                """,
                unsafe_allow_html=True
            )

with tab2:
    st.write("Backtest placeholder (signal vs DCA comparison)")