import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# ==========================================
# 系統初始化
# ==========================================
st.set_page_config(page_title="矛與盾 7.16 整合系統", page_icon="🛡️", layout="wide")
st.title("🛡️ 矛與盾 7.16 數據整合中心 ⚔️")

# ==========================================
# 工具函數
# ==========================================
def calculate_rsi(data, periods=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)
    avg_gain = gain.ewm(com=periods - 1, min_periods=periods).mean()
    avg_loss = loss.ewm(com=periods - 1, min_periods=periods).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def normalize_data(df):
    """標準化資料格式：統一欄位名、時區、移除重複"""
    if df.empty: return df
    df.index = pd.to_datetime(df.index).tz_localize(None)
    # 強制尋找 Close 欄位（不分大小寫）
    df.columns = [c.capitalize() for c in df.columns]
    if 'Close' not in df.columns:
        return pd.DataFrame()
    # 處理可能的多層 Index
    if isinstance(df['Close'], pd.DataFrame):
        df['Close'] = df['Close'].iloc[:, 0]
    return df[['Close', 'Vix']] if 'Vix' in df.columns else df[['Close']]

def process_metrics(df):
    """計算 SOP 0308 要求的各項指標"""
    df = df.copy().sort_index()
    if 'Vix' not in df.columns: df['Vix'] = 20.0
    df['RSI_14'] = calculate_rsi(df['Close'], periods=14)
    df['200_SMA'] = df['Close'].rolling(window=200, min_periods=1).mean()
    df['52W_High'] = df['Close'].rolling(window=52, min_periods=1).max()
    df['Drawdown'] = (df['Close'] - df['52W_High']) / df['52W_High']
    return df.dropna(subset=['Close', 'RSI_14'])

# ==========================================
# 核心數據處理引擎 (拼接邏輯)
# ==========================================
st.sidebar.header("📥 數據導入")
up_file = st.sidebar.file_uploader("1. 上傳歷史 CSV (選填)", type=['csv'])

if st.sidebar.button("🚀 執行全自動數據整合", type="primary"):
    with st.spinner("正在進行數據拼接與爬蟲對齊..."):
        df_final = pd.DataFrame()
        
        # A. 處理 CSV
        df_csv = pd.DataFrame()
        if up_file is not None:
            temp_csv = pd.read_csv(up_file, index_col=0, parse_dates=True)
            df_csv = normalize_data(temp_csv)
            if df_csv.empty: st.sidebar.error("CSV 格式不符(需含 Close)")

        # B. 執行爬蟲備援
        df_yf = pd.DataFrame()
        try:
            # 優先抓取最近 10 年
            v_raw = yf.Ticker("VOO").history(period="10y", interval="1wk")
            x_raw = yf.Ticker("^VIX").history(period="10y", interval="1wk")
            v_norm = normalize_data(v_raw)
            x_norm = normalize_data(x_raw)
            df_yf = pd.DataFrame({'Close': v_norm['Close'], 'Vix': x_norm['Close']}).dropna()
        except Exception as e:
            st.sidebar.warning(f"爬蟲暫時失效，將嘗試僅用 CSV。({e})")

        # C. 拼接邏輯 (拼接 CSV 與 YF，並去重複)
        if not df_csv.empty and not df_yf.empty:
            df_final = pd.concat([df_csv, df_yf])
            df_final = df_final[~df_final.index.duplicated(keep='last')].sort_index()
            st.sidebar.success("✅ CSV 與自動更新拼接成功")
        elif not df_csv.empty:
            df_final = df_csv
            st.sidebar.success("✅ 僅使用上傳之 CSV 數據")
        elif not df_yf.empty:
            df_final = df_yf
            st.sidebar.success("✅ 僅使用自動更新數據")
        
        if not df_final.empty:
            st.session_state['master'] = process_metrics(df_final)
        else:
            st.sidebar.error("❌ 無法獲取任何有效數據")

# ==========================================
# 顯示介面
# ==========================================
if 'master' in st.session_state:
    data = st.session_state['master']
    t1, t2 = st.tabs(["📊 監控面板", "⏳ 策略回測"])
    
    with t1:
        latest = data.iloc[-1]
        st.subheader(f"數據更新至：{latest.name.strftime('%Y-%m-%d')}")
        cost = st.number_input("您的 VOO 平均成本", value=450.0)
        
        c = st.columns(4)
        c[0].metric("VOO 價格", f"${latest['Close']:.2f}")
        c[1].metric("週 RSI", f"{latest['RSI_14']:.1f}")
        c[2].metric("VIX 指數", f"{latest['Vix']:.1f}")
        c[3].metric("距高點回撤", f"{latest['Drawdown']:.1%}")
        
        # SOP 邏輯判斷
        loss = (latest['Close'] - cost) / cost
        is_melt = loss < -0.15 or latest['Close'] < latest['200_SMA'] or latest['Vix'] > 40
        
        st.divider()
        if is_melt:
            st.error("🔴 狀態：熔斷模式啟動")
            st.info("執行：暫停 DCA。" + ("(RSI<30 允許單次加碼)" if latest['RSI_14'] < 30 else ""))
        else:
            st.success("🟢 狀態：系統正常運行")
            if latest['RSI_14'] < 35: st.warning("🔥 模式：提速扣款 + 額外加碼 (80萬)")
            elif latest['RSI_14'] < 45: st.warning("🟡 模式：提速扣款 (40萬)")
            else: st.info("🔵 模式：基礎扣款 (20萬)")

    with t2:
        if st.button("🚀 執行全量回測"):
            # 這裡放置您完整的 800萬/100萬 回測程式碼
            st.line_chart(data['Close'])
            st.write(f"數據量體：共 {len(data)} 筆週線紀錄")
else:
    st.info("請點擊左側「執行全自動數據整合」開始分析。")
