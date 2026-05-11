import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ====================== 1. CONFIG & CSS ======================
st.set_page_config(page_title="투자 신호등 V14.0", layout="wide")
st.markdown("""
    <style>
    .metric-card {
        background-color: #262730;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #4CAF50;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🚦 투자 신호등 V14.0 : SMA 50 기민한 대응")
st.markdown("> **SMA 50 기준: 시장의 작은 조정도 기회로 활용하여 수량을 극대화합니다.**")

# 종목별 변동성 가중치
RISK_MULTIPLIER = {
    "SOXL": 1.5, "TQQQ": 1.4, "TECL": 1.4, "SPXL": 1.2,
    "QQQ": 1.0, "SPY": 1.0, "SCHD": 0.8, "BRK-B": 0.8,
    "NVDA": 1.5, "TSLA": 1.5, "AAPL": 1.0, "MSFT": 1.0
}

groups = {
    "🚀 주력 레버리지": ["TQQQ", "SOXL", "QLD", "TECL"],
    "⚖️ 지수 및 배당": ["QQQ", "SPY", "SCHD", "VOO", "BRK-B"],
    "🔥 개별 성장주": ["NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "GOOGL"]
}
all_tickers = sum(groups.values(), [])

# ====================== 2. CORE DATA ENGINE ======================
@st.cache_data(ttl=3600)
def load_data(symbol, years=10):
    try:
        # 넉넉하게 데이터를 가져와서 SMA 50 계산에 차질 없게 함
        start = datetime.now() - timedelta(days=int(years * 365.25) + 100)
        df = yf.download(symbol, start=start, progress=False, auto_adjust=True)
        if df is None or df.empty or len(df) < 50: return None
        
        # yfinance Multi-index 방어
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        df = df[['Close']].dropna()
        return df
    except:
        return None

# ====================== 3. SMA 50 AGGI-STRATEGY ======================
def get_state_agile(disp_50):
    """
    SMA 50 괴리율 기반 공격적 배수 알고리즘
    - 과열 시 매수액을 1/10로 줄여 현금 집중 비축
    - 하락 시 비축 현금을 강력하게 투입
    """
    if disp_50 >= 0.12: return 0.1, "🔴 단기 과열 (극소량)"
    if disp_50 >= 0.06: return 0.4, "🟡 상승 경계 (절반 이하)"
    if disp_50 >= -0.04: return 1.0, "⚪ 중립 (정석 DCA)"
    if disp_50 >= -0.12: return 2.0, "🟢 조정 (적극 매수)"
    return 3.5, "🔵 폭락 (풀 매수)" # 폭락 시 배수를 3.5배로 상향

# ====================== 4. PERFORMANCE SIMULATOR ======================
def run_simulation(df, ticker, monthly_budget):
    price = df['Close']
    sma50 = price.rolling(50).mean() # 50일 이동평균
    ath = price.cummax()
    
    # 월말 종가 기준으로 리샘플링하여 적립식 시뮬레이션
    monthly_df = df.resample('ME').last()
    
    normal_shares = signal_shares = 0.0
    normal_inv = signal_inv = 0.0
    signal_cash_pool = 0.0

    for dt in monthly_df.index:
        if dt not in df.index: continue
        idx = df.index.get_loc(dt)
        if idx < 50: continue

        p = price.iloc[idx]
        curr_sma = sma50.iloc[idx]
        if pd.isna(curr_sma) or curr_sma == 0: continue
        
        # 50일 괴리율 계산
        disp_50 = (p - curr_sma) / curr_sma
        
        weight, _ = get_state_agile(disp_50)
        risk = RISK_MULTIPLIER.get(ticker, 1.0)
        final_weight = weight * risk

        # 1) 무지성 DCA
        normal_shares += monthly_budget / p
        normal_inv += monthly_budget

        # 2) 전략 DCA (현금 비축 및 투입 로직)
        if final_weight < 1.0:
            # 과열기: 정해진 비중만큼만 사고 나머지는 현금화
            buy_now = monthly_budget * final_weight
            save_now = monthly_budget - buy_now
            signal_shares += buy_now / p
            signal_cash_pool += save_now
        elif final_weight == 1.0:
            # 중립: 100% 매수
            signal_shares += monthly_budget / p
        else:
            # 하락기: 월 예산 + (비축 현금의 가중치 분량) 투입
            # 가중치가 높을수록 현금을 더 많이 소진
            deploy_rate = min((final_weight - 1.0) * 0.5, 1.0)
            bonus = signal_cash_pool * deploy_rate
            
            signal_shares += (monthly_budget + bonus) / p
            signal_cash_pool -= bonus
        
        signal_inv += monthly_budget

    final_price = price.iloc[-1]
    return {
        "normal_val": normal_shares * final_price,
        "signal_val": signal_shares * final_price + signal_cash_pool,
        "normal_inv": normal_inv,
        "signal_inv": signal_inv,
        "cash_left": signal_cash_pool
    }

# ====================== 5. MAIN UI ======================
with st.sidebar:
    st.header("⚙️ 시뮬레이션 설정")
    years = st.slider("데이터 기간 (년)", 3, 20, 10)
    monthly_budget = st.number_input("월 투자 예산 ($)", value=100)
    st.divider()
    st.write("SMA 50 기준은 200일 기준보다 훨씬 빈번한 매수 신호를 발생시킵니다.")

tab1, tab2 = st.tabs(["🚦 실시간 투자 지시등", "📈 전략 수익률 검증"])

# --- TAB 1: 실시간 상태 ---
with tab1:
    vix_data = load_data("^VIX", 1)
    vix_now = vix_data['Close'].iloc[-1] if vix_data is not None else 20.0
    st.subheader(f"현재 시장 변동성 (VIX): {vix_now:.2f}")

    for group_name, tickers in groups.items():
        st.markdown(f"### {group_name}")
        cols = st.columns(4)
        for i, t in enumerate(tickers):
            df_now = load_data(t, 1)
            if df_now is None: continue
            
            p = float(df_now['Close'].iloc[-1])
            sma50_val = float(df_now['Close'].rolling(50).mean().iloc[-1])
            disp = (p - sma50_val) / sma50_val if sma50_val != 0 else 0
            
            weight, state = get_state_agile(disp)
            risk = RISK_MULTIPLIER.get(t, 1.0)
            final_w = round(min(weight * risk, 5.0), 2) # 최대 5배까지 허용

            with cols[i % 4]:
                st.markdown(f"""
                <div style="padding:15px; border-radius:12px; background:#1E1E1E; border:1px solid #333; text-align:center; margin-bottom:15px;">
                    <span style="color:#888; font-size:14px;">{t}</span><br>
                    <span style="font-size:24px; font-weight:bold; color:#00FF00;">{final_w}x</span><br>
                    <span style="font-size:13px;">{state}</span>
                </div>
                """, unsafe_allow_html=True)

# --- TAB 2: 성능 검증 ---
with tab2:
    target = st.selectbox("수익률을 비교할 종목 선택", all_tickers)
    if st.button(f"{target} 전략 시뮬레이션 실행"):
        df_target = load_data(target, years)
        if df_target is not None:
            res = run_simulation(df_target, target, monthly_budget)
            
            n_roi = (res['normal_val'] - res['normal_inv']) / res['normal_inv'] * 100
            s_roi = (res['signal_val'] - res['signal_inv']) / res['signal_inv'] * 100
            
            st.subheader(f"📊 {target} : {years}년 적립식 성과 비교")
            
            c1, c2, c3 = st.columns(3)
            c1.metric("무지성 DCA 수익률", f"{n_roi:.1f}%")
            c2.metric("SMA 50 전략 수익률", f"{s_roi:.1f}%", f"{s_roi - n_roi:+.1f}%p")
            c3.metric("최종 자산 차이", f"${res['signal_val'] - res['normal_val']:,.0f}")
            
            st.divider()
            with st.expander("💡 전략 상세 로직 확인"):
                st.write(f"""
                - **종목:** {target} (가중치 {RISK_MULTIPLIER.get(target, 1.0)}배 적용)
                - **과열기:** 50일 이동평균보다 12% 이상 높으면 매수액을 90% 줄여 현금 비축
                - **폭락기:** 50일 이동평균보다 15% 이상 낮으면 비축 현금 전량 투입
                - **남은 현금:** 현재 전략 계좌에 `${res['cash_left']:,.2f}`의 현금이 대기 중입니다.
                """)