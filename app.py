import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ====================== CONFIG ======================

st.set_page_config(page_title="투자 신호등 V13.2 FINAL", layout="wide")
st.title("🚦 투자 신호등 V13.2 : 시장 상태 해석 시스템")

st.markdown("""
> 이 시스템은 자동매매가 아니라  
> 시장 상태를 해석하는 판단 보조 도구다.
""")

# ====================== RISK ======================

RISK_MULTIPLIER = {
    "SOXL": 1.5, "TQQQ": 1.3, "TECL": 1.3, "SPXL": 1.2,
    "QQQ": 1.0, "SPY": 1.0, "SCHD": 0.8, "BRK-B": 0.8
}

# ====================== PORTFOLIO ======================

groups = {
    "운용종목": ["QQQ", "TQQQ", "SOXL", "SCHD"],
    "관심종목": ["VOO", "SPY", "BRK-B", "VYM", "QLD", "NOBL", "SPXL", "SMH", "TECL", "AVUV", "JEPQ", "VGT"],
    "개별종목": ["MSFT", "GOOGL", "TSLA", "AMZN", "NVDA", "AMD"]
}

all_tickers = sum(groups.values(), [])

# ====================== DATA ======================

@st.cache_data(ttl=3600)
def load_data(symbol, years=10):
    try:
        start = datetime.now() - timedelta(days=int(years * 365.25))
        df = yf.download(symbol, start=start, progress=False, auto_adjust=True)

        if df is None or df.empty or len(df) < 200:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        return df[['Close']].dropna()

    except:
        return None

# ====================== SIGNAL ======================

def get_state(mdd, mom, disp):
    if mom >= 0.10 and disp >= 0.20:
        return 0.3, "🔴 과열"
    if mom >= 0.05:
        return 0.7, "🟡 상승 경계"
    if mdd > -0.10:
        return 1.0, "⚪ 정상"
    if mdd > -0.30:
        return 1.5, "🟢 조정"
    return 2.5, "🔵 폭락"

# ====================== BACKTEST FIX ======================

def run_simulation(df, vix_df, ticker, monthly_budget):

    price = df['Close']
    vix = vix_df['Close'].reindex(df.index, method='ffill')

    sma200 = price.rolling(200, min_periods=200).mean()
    ath = price.cummax()

    # 🚀 안정적인 월말 인덱스
    monthly_idx = price.index.to_series().groupby(
        [price.index.year, price.index.month]
    ).max().values

    normal_shares = 0.0
    signal_shares = 0.0
    normal_inv = 0.0
    signal_inv = 0.0

    for dt in monthly_idx:

        if dt not in price.index:
            continue

        idx = price.index.get_loc(dt)

        if idx < 200:
            continue

        p = price.iloc[idx]

        ath_val = ath.iloc[idx]
        sma_val = sma200.iloc[idx]

        if pd.isna(p) or pd.isna(ath_val) or pd.isna(sma_val):
            continue

        if ath_val == 0 or sma_val == 0:
            continue

        mdd = (p - ath_val) / ath_val
        mom = (p - price.iloc[idx-22]) / price.iloc[idx-22] if idx >= 22 else 0
        disp = (p - sma_val) / sma_val

        weight, _ = get_state(mdd, mom, disp)

        # DCA
        normal_shares += monthly_budget / p
        normal_inv += monthly_budget

        # weighted DCA
        signal_shares += (monthly_budget * weight) / p
        signal_inv += (monthly_budget * weight)

    final_price = price.iloc[-1]

    if normal_inv == 0 or signal_inv == 0:
        return {
            "normal_val": 0,
            "signal_val": 0,
            "normal_inv": 0,
            "signal_inv": 0
        }

    return {
        "normal_val": normal_shares * final_price,
        "signal_val": signal_shares * final_price,
        "normal_inv": normal_inv,
        "signal_inv": signal_inv
    }

# ====================== UI ======================

with st.sidebar:
    years = st.slider("분석 기간", 3, 15, 10)
    monthly_budget = st.number_input("월 투자금 ($)", value=100)

vix_df = load_data("^VIX", years)
vix_now = vix_df['Close'].iloc[-1] if vix_df is not None else 20.0

tab1, tab2 = st.tabs(["🚦 시장 상태", "📊 전략 검증"])

# ====================== TAB 1 ======================

with tab1:
    st.subheader(f"현재 VIX: {vix_now:.2f}")

    for group_name, ticker_list in groups.items():
        st.markdown(f"### {group_name}")

        cols = st.columns(2)

        for i, t in enumerate(ticker_list):

            df = load_data(t, 2)
            if df is None:
                continue

            p = df['Close'].iloc[-1]
            sma200 = df['Close'].rolling(200).mean().iloc[-1]
            ath = df['Close'].cummax().iloc[-1]

            mdd = (p - ath) / ath
            mom = (p - df['Close'].iloc[-22]) / df['Close'].iloc[-22]
            disp = (p - sma200) / sma200 if not pd.isna(sma200) else 0

            weight, state = get_state(mdd, mom, disp)

            final_weight = round(min(weight * RISK_MULTIPLIER.get(t, 1.0), 3.0), 2)

            with cols[i % 2]:
                st.markdown(f"""
                <div style="padding:14px;border-radius:12px;background:#222;color:white;text-align:center;">
                    <b>{t}</b><br>
                    <div style="font-size:22px;">{final_weight}x</div>
                    <small>{state}</small>
                </div>
                """, unsafe_allow_html=True)

# ====================== TAB 2 ======================

with tab2:

    target = st.selectbox("종목 선택", all_tickers)

    if st.button("시스템 비교 실행"):

        df = load_data(target, years)

        if df is not None and vix_df is not None:

            res = run_simulation(df, vix_df, target, monthly_budget)

            normal_roi = (res['normal_val'] - res['normal_inv']) / res['normal_inv'] * 100
            signal_roi = (res['signal_val'] - res['signal_inv']) / res['signal_inv'] * 100

            st.subheader("📊 DCA vs 상태 기반 전략 비교")

            c1, c2, c3 = st.columns(3)

            c1.metric("무지성 DCA", f"{normal_roi:.1f}%")
            c2.metric("신호 기반 DCA", f"{signal_roi:.1f}%", f"{signal_roi - normal_roi:+.1f}%p")
            c3.metric("초과 자산", f"${res['signal_val'] - res['normal_val']:,.0f}")