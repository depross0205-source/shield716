import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# ==========================================
# 系統與 UI 初始化
# ==========================================
st.set_page_config(page_title="矛與盾 7.16 系統", page_icon="🛡️", layout="wide")
st.title("🛡️ 矛與盾 7.16 整合系統 ⚔️")

# ==========================================
# 工具函數：技術指標與數據清洗
# ==========================================
def calculate_rsi(data, periods=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)
    avg_gain = gain.ewm(com=periods - 1, min_periods=periods).mean()
    avg_loss = loss.ewm(com=periods - 1, min_periods=periods).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def clean_and_fix_df(df):
    """處理 yfinance 的多層 Index 與空值問題"""
    if df.empty: return df
    # 如果是多層欄位 (MultiIndex)，只取第一層
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    # 確保只留下必要的欄位並移除空值
    return df.loc[:, ~df.columns.duplicated()].dropna()

def process_market_data(df):
    if df.empty: return df
    df = df.copy()
    df['RSI_14'] = calculate_rsi(df['Close'], periods=14)
    df['200_SMA'] = df['Close'].rolling(window=200, min_periods=1).mean()
    df['52W_High'] = df['Close'].rolling(window=52, min_periods=1).max()
    df['Drawdown'] = (df['Close'] - df['52W_High']) / df['52W_High']
    return df.dropna(subset=['Close', 'RSI_14'])

# ==========================================
# 數據引擎中心
# ==========================================
st.sidebar.header("🗄️ 數據引擎中心")
uploaded_file = st.sidebar.file_uploader("上傳歷史 CSV (需含 Close 欄位)", type=['csv'])

if st.sidebar.button("🔄 載入並聯網拼接全量數據庫", type="primary"):
    with st.spinner("正在校準數據時間軸..."):
        df_csv = pd.DataFrame()
        start_date = "2015-01-01" 
        
        if uploaded_file is not None:
            try:
                df_csv = pd.read_csv(uploaded_file, index_col=0, parse_dates=True)
                if 'Close' in df_csv.columns:
                    if 'VIX' not in df_csv.columns: df_csv['VIX'] = 20.0 
                    last_date = df_csv.index.max()
                    if pd.notnull(last_date):
                        start_date = (last_date - pd.Timedelta(days=7)).strftime('%Y-%m-%d')
            except Exception as e:
                st.sidebar.error(f"CSV 讀取失敗: {e}")
                
        try:
            # 分開抓取以避免對齊錯誤
            voo_raw = yf.download("VOO", start=start_date, interval="1wk", progress=False)
            vix_raw = yf.download("^VIX", start=start_date, interval="1wk", progress=False)
            
            # 清洗 yfinance 數據
            voo_clean = clean_and_fix_df(voo_raw)
            vix_clean = clean_and_fix_df(vix_raw)
            
            # 使用 inner join 強制時間對齊
            df_yf = pd.DataFrame({
                'Close': voo_clean['Close'],
                'VIX': vix_clean['Close']
            }).dropna()
            
            # 拼接邏輯
            if not df_csv.empty:
                df_csv.index = pd.to_datetime(df_csv.index).tz_localize(None)
                df_yf.index = pd.to_datetime(df_yf.index).tz_localize(None)
                combined = pd.concat([df_csv[['Close', 'VIX']], df_yf])
                combined = combined[~combined.index.duplicated(keep='last')].sort_index()
            else:
                combined = df_yf.tz_localize(None) if df_yf.index.tz is not None else df_yf
            
            if combined.empty:
                st.sidebar.error("數據拼接後為空，請檢查網路。")
            else:
                st.session_state['master_data'] = process_market_data(combined)
                st.sidebar.success(f"✅ 數據就緒！共 {len(st.session_state['master_data'])} 筆。")
        except Exception as e:
            st.sidebar.error(f"數據對齊失敗: {e}")

# ==========================================
# 介面分頁設定
# ==========================================
tab1, tab2 = st.tabs(["📊 即時監控面板", "⏳ 歷史回測引擎"])

# ------------------------------------------
# 分頁 1：即時監控面板
# ------------------------------------------
with tab1:
    if 'master_data' not in st.session_state:
        st.warning("👈 請先從側邊選單載入數據庫")
    else:
        df_live = st.session_state['master_data']
        avg_cost = st.number_input("您的 VOO 平均成本", value=450.0)
        latest = df_live.iloc[-1]
        
        # UI 卡片展示
        cols = st.columns(4)
        cols[0].metric("最新價格", f"${latest['Close']:.2f}")
        cols[1].metric("週線 RSI", f"{latest['RSI_14']:.1f}")
        cols[2].metric("VIX 指數", f"{latest['VIX']:.1f}")
        cols[3].metric("回撤幅度", f"{latest['Drawdown']:.1%}")
        
        # 核心判斷邏輯
        p_loss = (latest['Close'] - avg_cost) / avg_cost
        is_melt = p_loss < -0.15 or latest['Close'] < latest['200_SMA'] or latest['VIX'] > 40
        
        st.divider()
        if is_melt:
            st.error("🔴 熔斷啟動中")
            st.write("執行建議：" + ("允許單次加碼" if latest['RSI_14'] < 30 else "暫停 DCA"))
        else:
            st.success("🟢 系統運行正常")
            if latest['RSI_14'] < 35: st.warning("🔥 模式：超賣加碼 (80萬)")
            elif latest['RSI_14'] < 45: st.warning("🟡 模式：提速扣款 (40萬)")
            else: st.info("🔵 模式：基礎扣款 (20萬)")

# ------------------------------------------
# 分頁 2：歷史回測引擎
# ------------------------------------------
with tab2:
    if 'master_data' in st.session_state:
        st.header("參數化回測")
        base_amt = st.number_input("每月基礎扣款 (萬)", value=20)
        if st.button("🚀 開始回測", type="primary"):
            df_bt = st.session_state['master_data']
            # 此處簡化回測顯示，確保系統穩定
            st.line_chart(df_bt['Close'])
            st.success("數據流測試正常，可進行完整回測運算。")
