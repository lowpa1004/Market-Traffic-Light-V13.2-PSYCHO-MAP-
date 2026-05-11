import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ====================== CONFIG ======================
st.set_page_config(page_title="투자 신호등 V13 FIXED", layout="wide")
st.title("🚦 투자 신호등 V13 FIXED")

st.markdown("""
> 시장 상태를 해석하는 **참고용 신호 시스템**
> (자동매매 아님 / 판단 보조 도구)
""")

# ====================== 종목 구조 ======================
groups = {
    "📌 운용종목": ["QQQ", "TQQQ", "SOXL", "SCHD"],
    "📌 관심종목": ["VOO", "SPY", "BRK-B", "VYM", "QLD", "NOBL", "SPXL", "SMH", "TECL", "AVUV", "JEPQ", "VGT"],
    "📌 개별종목": ["MSFT", "GOOGL", "TSLA", "AMZN", "NVDA", "AMD"]
}

RISK_MULTIPLIER = {
    "SOXL": 1.5, "TQQQ": 1.3, "TECL": 1.3, "SPXL": 1.2,
    "QQQ": 1.0, "SPY": 1.0, "SCHD": 0.8, "BRK-B": 0.8
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

        # 🔥 핵심 안정화
        df = df.copy()
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        df = df[['Close']].dropna()

        return df

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


# ====================== SIMULATION ======================
def run_simulation(df, vix_df, ticker, monthly_budget):

    price = df['Close']
    vix = vix_df['Close'].reindex(df.index, method='ffill')

    sma200 = price.rolling(200, min_periods=200).mean()
    ath = price.cummax()

    # 🔥 핵심 안정화 (resample 에러 제거)
    monthly_idx = df.resample('ME').last().index

    normal_shares = 0
    signal_shares = 0
    normal_inv = 0
    signal_inv = 0

    for dt in monthly_idx:
        if dt not in df.index:
            continue

        idx = df.index.get_loc(dt)
        if idx < 200:
            continue

        p = price.iloc[idx]

        # 안전 처리
        if idx < 22:
            continue

        mdd = (p - ath.iloc[idx]) / ath.iloc[idx]
        mom = (p - price.iloc[idx-22]) / price.iloc[idx-22]

        if pd.isna(sma200.iloc[idx]) or sma200.iloc[idx] == 0:
            continue

        disp = (p - sma200.iloc[idx]) / sma200.iloc[idx]

        weight, _ = get_state(mdd, mom, disp)

        risk = RISK_MULTIPLIER.get(ticker, 1.0)
        final_weight = min(weight * risk, 3.0)

        # DCA
        normal_shares += monthly_budget / p
        normal_inv += monthly_budget

        signal_shares += (monthly_budget * final_weight) / p
        signal_inv += (monthly_budget * final_weight)

    final_price = price.iloc[-1]

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
vix_now = vix_df['Close'].iloc[-1] if vix_df is not None else 20


tab1, tab2 = st.tabs(["🚦 시장 상태", "📊 전략 검증"])


# ====================== TAB 1 ======================
with tab1:
    st.subheader(f"현재 VIX: {vix_now:.2f}")

    for group_name, ticker_list in groups.items():
        st.markdown(f"### {group_name}")

        cols = st.columns(2)  # 모바일 대응 핵심

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

            risk = RISK_MULTIPLIER.get(t, 1.0)
            final_weight = round(min(weight * risk, 3.0), 2)

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

            st.subheader("📊 DCA 비교")

            c1, c2, c3 = st.columns(3)
            c1.metric("무지성 DCA", f"{normal_roi:.1f}%")
            c2.metric("신호 DCA", f"{signal_roi:.1f}%", f"{signal_roi - normal_roi:+.1f}%p")
            c3.metric("초과 자산", f"${res['signal_val'] - res['normal_val']:,.0f}")