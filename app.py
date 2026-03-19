import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, date

# ==========================================
# 系統初始化 (信心程度：10 分)
# ==========================================
st.set_page_config(page_title="矛與盾 7.50 因子整合版", page_icon="🛡️", layout="wide")
st.title("🛡️ 矛與盾 7.50 四大因子量化系統 ⚔️")

# ==========================================
# 工具函數：數據強力對齊
# ==========================================
def normalize_columns(df):
    """【因子全保留】強力對齊 SP500, SP500EW, VIX, CAPE"""
    if df.empty: return df
    df = df.reset_index()
    df.columns = [str(c).strip() for c in df.columns]
    upper_cols = [c.upper() for c in df.columns]
    
    # 定義模糊匹配關鍵字
    mapping = {
        'Close': ['SP500', 'VOO', 'CLOSE', 'PRICE', '價格', '收盤'],
        'SP500EW': ['RSP', 'EW', '等權重', 'SP500EW'],
        'Vix': ['VIX', '恐慌', 'CBOE', '^VIX'],
        'Cape': ['CAPE', '席勒', '本益比']
    }
    
    for target, kws in mapping.items():
        for i, col in enumerate(upper_cols):
            if any(kw in col for kw in kws) and target not in df.columns:
                df[target] = pd.to_numeric(df.iloc[:, i].astype(str).str.replace(',', '').str.replace('$', ''), errors='coerce')
                st.sidebar.success(f"✅ 因子對齊：{df.columns[i]} -> {target}")
                
    return df

def get_base_data(start, end):
    """聯網抓取三大指數：VOO, RSP, VIX"""
    with st.spinner("正在聯網校準 SP500、等權重與 VIX 數據..."):
        # 抓取 SPY (2010前代理), VOO, RSP (等權重), VIX
        spy = yf.Ticker("SPY").history(start=start, end=end, interval="1wk")
        voo = yf.Ticker("VOO").history(start=start, end=end, interval="1wk")
        rsp = yf.Ticker("RSP").history(start=start, end=end, interval="1wk")
        vix = yf.Ticker("^VIX").history(start=start, end=end, interval="1wk")
        
        for d in [spy, voo, rsp, vix]:
            if not d.empty: d.index = d.index.tz_localize(None)
            
        # 價格縫合邏輯 (SPY 模擬 VOO)
        if voo.empty:
            full_voo = spy[['Close']] * 0.9 
        else:
            common = voo.index[0]
            ratio = voo.at[common, 'Close'] / spy.at[common, 'Close'] if common in spy.index else 0.9
            pre_voo = spy[:common].iloc[:-1][['Close']] * ratio
            full_voo = pd.concat([pre_voo, voo[['Close']]])
        
        # 建立 Web 基準表
        web_df = pd.DataFrame(index=spy.index)
        web_df['Close_Web'] = full_voo['Close']
        web_df['SP500EW_Web'] = rsp['Close']
        web_df['Vix_Web'] = vix['Close']
        web_df.index.name = 'Date_Final'
        return web_df.reset_index()

# ==========================================
# 側邊欄與數據導入
# ==========================================
st.sidebar.header("📊 系統參數設定")
start_d = st.sidebar.date_input("回測起始日", date(2003, 5, 1))
end_d = st.sidebar.date_input("回測結束日", date.today())
init_funds = st.sidebar.number_input("初始總資金 (NTD)", value=9000000)
base_dca = st.sidebar.number_input("每月 DCA 基數", value=200000)
confirm_w = st.sidebar.slider("訊號連續週數確認", 1, 5, 1)

up_file = st.sidebar.file_uploader("📥 上傳 CSV (需含 CAPE 等因子)", type=['csv'])

if st.sidebar.button("🔄 執行全因子強力整合", type="primary"):
    web_df = get_base_data(start_d, end_d)
    
    if up_file:
        df_csv = normalize_columns(pd.read_csv(up_file))
        date_col = next((c for c in df_csv.columns if any(k in str(c).upper() for k in ['DATE', 'TIME', '日期'])), None)
        
        if date_col:
            df_csv['Date_Final'] = pd.to_datetime(df_csv[date_col], errors='coerce')
            web_df['Date_Final'] = pd.to_datetime(web_df['Date_Final'], errors='coerce')
            
            # 使用 Outer Join 確保 CAPE、Spread 等因子全部保留
            final_df = pd.merge(web_df, df_csv, on='Date_Final', how='outer')
            
            # 優先權：CSV 數據 > Web 數據
            for target in ['Close', 'SP500EW', 'Vix']:
                web_col = f"{target}_Web" if target != 'SP500EW' else "SP500EW_Web"
                if target not in final_df.columns:
                    final_df[target] = final_df[web_col]
                else:
                    final_df[target] = final_df[target].combine_first(final_df[web_col])
            
            final_df = final_df.rename(columns={'Date_Final': 'Date'})
        else:
            st.error("❌ CSV 找不到日期標籤")
            final_df = web_df.rename(columns={'Date_Final': 'Date', 'Close_Web': 'Close', 'Vix_Web': 'Vix'})
    else:
        final_df = web_df.rename(columns={'Date_Final': 'Date', 'Close_Web': 'Close', 'SP500EW_Web': 'SP500EW', 'Vix_Web': 'Vix'})

    # 排序並儲存
    if 'Date' in final_df.columns:
        final_df = final_df.sort_values('Date').dropna(subset=['Date'])
        st.session_state['merged_df'] = final_df
    else:
        st.error("❌ 無法建立日期索引")

# ==========================================
# 數據補強與回測
# ==========================================
if 'merged_df' in st.session_state:
    master = st.session_state['merged_df']
    # 檢查四大因子是否齊全
    factors = ['Close', 'SP500EW', 'Vix', 'Cape']
    existing_factors = [f for f in factors if f in master.columns]
    mask = master[existing_factors].isna().any(axis=1)
    missing = master[mask]

    if not missing.empty:
        st.warning(f"⚠️ 偵測到有 {len(missing)} 筆核心因子缺失，請在此修正：")
        corrected = st.data_editor(missing, num_rows="fixed", use_container_width=True)
        if st.button("💾 儲存並執行深度回測"):
            master.update(corrected)
            st.session_state['merged_df'] = master
            st.rerun()
    else:
        st.success("✨ 四大因子 (SP500, SP500EW, VIX, CAPE) 已完整對齊！")

    if st.button("🚀 啟動量化策略回測"):
        df_final = master.copy().set_index('Date').ffill().bfill()
        
        # 指標計算
        def calculate_rsi(data, periods=14):
            delta = data.diff(); g = delta.where(delta > 0, 0); l = -delta.where(delta < 0, 0)
            avg_g = g.ewm(com=periods-1, min_periods=periods).mean()
            avg_l = l.ewm(com=periods-1, min_periods=periods).mean()
            return 100 - (100 / (1 + (avg_g / (avg_l + 1e-9))))

        df_final['RSI'] = calculate_rsi(df_final['Close'])
        df_final['SMA_200'] = df_final['Close'].rolling(window=200, min_periods=1).mean()
        df_final['Drawdown'] = (df_final['Close'] - df_final['Close'].rolling(window=52, min_periods=1).max()) / df_final['Close'].rolling(window=52, min_periods=1).max()
        
        st.session_state['master'] = df_final[start_d:end_d]
        st.write("### 終極因子數據表 (最後 10 筆)：")
        # 確保顯示順序，將核心因子排在前面
        display_cols = ['Close', 'SP500EW', 'Vix', 'Cape', 'RSI', 'Drawdown'] + [c for c in df_final.columns if c not in factors + ['RSI', 'Drawdown']]
        st.dataframe(df_final[display_cols].tail(10))
