import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ====================== CONFIG ======================
st.set_page_config(page_title="투자 신호등 V13.5", layout="wide")
st.title("🚦 투자 신호등 V13.5 : 수익률 최적화 엔진")

RISK_MULTIPLIER = {
    "SOXL": 1.5, "TQQQ": 1.3, "TECL": 1.3, "SPXL": 1.2,
    "QQQ": 1.0, "SPY": 1.0, "SCHD": 0.8, "BRK-B": 0.8
}

groups = {
    "운용종목": ["QQQ", "TQQQ", "SOXL", "SCHD"],
    "관심종목": ["VOO", "SPY", "BRK-B", "VYM", "QLD", "NOBL", "SPXL", "SMH", "TECL", "AVUV", "JEPQ", "VGT"],
    "개별종목": ["MSFT", "GOOGL", "TSLA", "AMZN", "NVDA", "AMD"]
}
all_tickers = sum(groups.values(), [])

# ====================== DATA ENGINE ======================
@st.cache_data(ttl=3600)
def load_data(symbol, years=10):
    try:
        start = datetime.now() - timedelta(days=int(years * 365.25))
        df = yf.download(symbol, start=start, progress=False, auto_adjust=True)
        if df is None or df.empty or len(df) < 200: return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df[['Close']].dropna()
    except: return None

# ====================== SIGNAL LOGIC ======================
def get_state(mdd, mom, disp):
    if mom >= 0.10 and disp >= 0.20: return 0.3, "🔴 과열"
    if mom >= 0.05: return 0.7, "🟡 상승"
    if mdd > -0.10: return 1.0, "⚪ 중립"
    if mdd > -0.25: return 1.5, "🟢 조정" # 조정 구간 매수 강도 강화
    return 2.5, "🔵 폭락"

# ====================== OPTIMIZED SIMULATION ======================
def run_simulation(df, ticker, monthly_budget):
    price = df['Close']
    sma200 = price.rolling(200).mean()
    ath = price.cummax()
    monthly_idx = df.resample('ME').last().index

    normal_shares = signal_shares = 0.0
    normal_inv = signal_inv = 0.0
    signal_cash_pool = 0.0

    for dt in monthly_idx:
        if dt not in df.index: continue
        idx = df.index.get_loc(dt)
        if idx < 200: continue

        p = price.iloc[idx]
        mdd = (p - ath.iloc[idx]) / ath.iloc[idx]
        mom = (p - price.iloc[idx-22]) / price.iloc[idx-22]
        disp = (p - sma200.iloc[idx]) / sma200.iloc[idx] if not pd.isna(sma200.iloc[idx]) else 0
        
        weight, _ = get_state(mdd, mom, disp)

        # 1. 무지성 DCA (비교군)
        normal_shares += monthly_budget / p
        normal_inv += monthly_budget

        # 2. 전략 DCA (개선된 수익률 역전 로직)
        # [핵심] 과열기에도 50%는 사서 수량을 확보하고, 나머지를 저축함
        if weight <= 0.7:
            buy_amt = monthly_budget * 0.5  # 50% 매수
            save_amt = monthly_budget * 0.5 # 50% 저축
            signal_shares += buy_amt / p
            signal_cash_pool += save_amt
        
        # 중립 구간 (100% 매수)
        elif 0.7 < weight < 1.5:
            signal_shares += monthly_budget / p
            
        # 조정 및 폭락 구간 (기본금 + 저축한 현금 투입)
        else:
            # 🔵 조정 시 현금의 50%, 폭락 시 현금의 100% 투입
            deploy_rate = 1.0 if weight >= 2.5 else 0.5
            bonus = signal_cash_pool * deploy_rate
            
            buy_amt = monthly_budget + bonus
            signal_shares += buy_amt / p
            signal_cash_pool -= bonus
        
        signal_inv += monthly_budget

    final_p = price.iloc[-1]
    return {
        "normal_val": normal_shares * final_p,
        "signal_val": signal_shares * final_p + signal_cash_pool,
        "normal_inv": normal_inv,
        "signal_inv": signal_inv
    }

# ====================== UI ======================
with st.sidebar:
    years = st.slider("분석 기간", 3, 15, 10)
    monthly_budget = st.number_input("월 투자금 ($)", value=100)

vix_df = load_data("^VIX", 1)
vix_now = vix_df['Close'].iloc[-1] if vix_df is not None else 20

tab1, tab2 = st.tabs(["🚦 시장 상태", "📊 전략 성능 검증"])

with tab1:
    st.subheader(f"현재 VIX: {vix_now:.2f}")
    cols = st.columns(4)
    for i, t in enumerate(all_tickers):
        df_mini = load_data(t, 2)
        if df_mini is None: continue
        p = df_mini['Close'].iloc[-1]
        sma = df_mini['Close'].rolling(200).mean().iloc[-1]
        ath = df_mini['Close'].cummax().iloc[-1]
        mdd = (p - ath) / ath
        mom = (p - df_mini['Close'].iloc[-22]) / df_mini['Close'].iloc[-22]
        disp = (p - sma) / sma if not pd.isna(sma) else 0
        weight, state = get_state(mdd, mom, disp)
        final_w = round(min(weight * RISK_MULTIPLIER.get(t, 1.0), 3.0), 2)
        with cols[i % 4]:
            st.markdown(f"""<div style="padding:14px;border-radius:12px;background:#222;color:white;text-align:center;margin-bottom:10px;">
                <b>{t}</b><br><div style="font-size:22px;color:#00ff00;">{final_w}x</div><small>{state}</small></div>""", unsafe_allow_html=True)

with tab2:
    target = st.selectbox("종목 선택", all_tickers)
    if st.button("전략 시뮬레이션 실행"):
        df_sim = load_data(target, years)
        if df_sim is not None:
            res = run_simulation(df_sim, target, monthly_budget)
            n_roi = (res['normal_val'] - res['normal_inv']) / res['normal_inv'] * 100
            s_roi = (res['signal_val'] - res['signal_inv']) / res['signal_inv'] * 100
            
            c1, c2, c3 = st.columns(3)
            c1.metric("무지성 DCA", f"{n_roi:.1f}%")
            c2.metric("전략 DCA", f"{s_roi:.1f}%", f"{s_roi - n_roi:+.1f}%p")
            c3.metric("최종 자산 차이", f"${res['signal_val'] - res['normal_val']:,.0f}")
            
            st.info(f"💡 전략: 과열기에 현금 50% 세이브 → 폭락기에 세이브한 현금 {target}에 집중 투하")