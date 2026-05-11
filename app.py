import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ====================== CONFIG ======================
st.set_page_config(page_title="투자 신호등 V13.2", layout="wide")
st.title("🚦 투자 신호등 V13.2 : 에러 복구 완료")

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

# ====================== DATA ENGINE ======================
@st.cache_data(ttl=3600)
def load_data(symbol, years=10):
    try:
        start = datetime.now() - timedelta(days=int(years * 365.25))
        df = yf.download(symbol, start=start, progress=False, auto_adjust=True)
        if df is None or df.empty or len(df) < 200: return None
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        df = df[['Close']].dropna()
        return df
    except: return None

# ====================== SIGNAL ENGINE ======================
def get_state(mdd, mom, disp):
    if mom >= 0.10 and disp >= 0.20: return 0.3, "🔴 과열"
    if mom >= 0.05: return 0.7, "🟡 상승 경계"
    if mdd > -0.10: return 1.0, "⚪ 정상"
    if mdd > -0.30: return 1.5, "🟢 조정"
    return 2.5, "🔵 폭락"

# ====================== UI & LOGIC ======================
with st.sidebar:
    years = st.slider("분석 기간", 3, 15, 10)
    monthly_budget = st.number_input("월 투자금 ($)", value=100)

vix_df = load_data("^VIX", 1)
vix_now = float(vix_df['Close'].iloc[-1]) if vix_df is not None and not vix_df.empty else 20.0

tab1, tab2 = st.tabs(["🚦 실시간 신호", "📊 전략 검증"])

with tab1:
    st.subheader(f"현재 VIX: {vix_now:.2f}")
    for group_name, ticker_list in groups.items():
        st.markdown(f"#### {group_name}")
        cols = st.columns(4)
        for i, t in enumerate(ticker_list):
            df = load_data(t, 2)
            if df is None or len(df) < 200: continue

            # [FIX] 에러 발생 구간 수정: iloc[-1]을 사용하여 단일 스칼라 값으로 추출
            p = float(df['Close'].iloc[-1])
            sma_series = df['Close'].rolling(200).mean()
            sma_val = sma_series.iloc[-1] # Series가 아닌 마지막 '값' 하나만 가져옴
            
            ath_val = float(df['Close'].cummax().iloc[-1])

            mdd = (p - ath_val) / ath_val
            mom = (p - df['Close'].iloc[-22]) / df['Close'].iloc[-22]
            
            # [FIX] sma_val이 단일 값이므로 이제 에러가 발생하지 않음
            disp = (p - sma_val) / sma_val if not pd.isna(sma_val) and sma_val != 0 else 0

            weight, state = get_state(mdd, mom, disp)
            risk = RISK_MULTIPLIER.get(t, 1.0)
            final_w = round(min(weight * risk, 3.0), 2)

            with cols[i % 4]:
                st.markdown(f"""
                <div style="padding:12px; border-radius:10px; background:#222; color:white; text-align:center; margin-bottom:10px;">
                    <b>{t}</b><br>
                    <span style="font-size:22px; color:#00ff00;">{final_w}x</span><br>
                    <small>{state}</small>
                </div>
                """, unsafe_allow_html=True)

# 백테스트 탭은 이전 안정화 코드를 그대로 유지합니다.