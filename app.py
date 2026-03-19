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
st.set_page_config(page_title="矛與盾 7.45 因子全保留版", page_icon="🛡️", layout="wide")
st.title("🛡️ 矛與盾 7.45 數據因子全保留系統 ⚔️")

# ==========================================
# 工具函數：強力標準化
# ==========================================
def normalize_columns(df):
    """【因子全保留】強力對齊價格與 VIX，同時保留所有原始欄位"""
    if df.empty: return df
    
    # 1. 釋放索引並清理欄位名
    df = df.reset_index()
    # 暫存原始欄位名以便比對，但不更動原始 dataframe
    orig_cols = df.columns.tolist()
    upper_cols = [str(c).strip().upper() for c in orig_cols]
    
    # 2. 定義模糊匹配關鍵字
    price_kws = ['SP500', 'CLOSE', 'PRICE', 'VOO', '價格', '收盤', 'VALUE']
    vix_kws = ['VIX', '恐慌', 'CBOE', '^VIX']
    
    # 3. 強力尋找並建立系統統一欄位 (Close & Vix)
    target_price_idx = -1
    for i, col in enumerate(upper_cols):
        if any(kw in col for kw in price_kws):
            target_price_idx = i
            break
            
    if target_price_idx != -1:
        orig_name = orig_cols[target_price_idx]
        df['Close'] = pd.to_numeric(df[orig_name].astype(str).str.replace(',', '').str.replace('$', ''), errors='coerce')
        st.sidebar.success(f"✅ 價格對齊：{orig_name} -> Close")

    target_vix_idx = -1
    for i, col in enumerate(upper_cols):
        if any(kw in col for kw in vix_kws):
            target_vix_idx = i
            break
            
    if target_vix_idx != -1:
        orig_vix_name = orig_cols[target_vix_idx]
        df['Vix'] = pd.to_numeric(df[orig_vix_name].astype(str).str.replace(',', ''), errors='coerce')
        st.sidebar.success(f"✅ VIX 對齊：{orig_vix_name} -> Vix")
    
    return df

def get_base_data(start, end):
    """獲取聯網數據作為時間軸基準"""
    with st.spinner("正在聯網校準數據時間軸..."):
        # 抓取 SPY 作為 2003-2010 的代理
        spy = yf.Ticker("SPY").history(start=start, end=end, interval="1wk")
        voo = yf.Ticker("VOO").history(start=start, end=end, interval="1wk")
        vix = yf.Ticker("^VIX").history(start=start, end=end, interval="1wk")
        
        spy.index = spy.index.tz_localize(None)
        voo.index = voo.index.tz_localize(None)
        vix.index = vix.index.tz_localize(None)
        
        # 數據縫合
        if voo.empty:
            full_voo = spy[['Close']] * 0.9 
        else:
            common = voo.index[0]
            if common in spy.index:
                ratio = voo.at[common, 'Close'] / spy.at[common, 'Close']
                pre_voo = spy[:common].iloc[:-1][['Close']] * ratio
                full_voo = pd.concat([pre_voo, voo[['Close']]])
            else:
                full_voo = voo[['Close']]
        
        web_df = pd.DataFrame(index=spy.index)
        web_df['Close_Web'] = full_voo['Close']
        web_df['Vix_Web'] = vix['Close']
        return web_df.reset_index().rename(columns={'Date': 'Date_Final'})

# ==========================================
# 主邏輯執行
# ==========================================
st.sidebar.header("📊 系統控制中心")
start_d = st.sidebar.date_input("回測起始日", date(2003, 5, 1))
end_d = st.sidebar.date_input("回測結束日", date.today())
init_core = st.sidebar.number_input("核心初始資金", value=8000000)
init_rsv = st.sidebar.number_input("預備金總額", value=1000000)
base_dca = st.sidebar.number_input("基礎月扣額", value=200000)
confirm_w = st.sidebar.slider("訊號連續週數確認", 1, 5, 1)

up_file = st.sidebar.file_uploader("📥 上傳 CSV 數據", type=['csv'])

if st.sidebar.button("🔄 執行全數據強力整合", type="primary"):
    web_df = get_base_data(start_d, end_d)
    
    if up_file:
        df_csv = pd.read_csv(up_file)
        df_csv = normalize_columns(df_csv)
        
        # 尋找日期欄位
        date_col = None
        for col in df_csv.columns:
            if any(kw in str(col).upper() for kw in ['DATE', 'TIME', '日期', '時間']):
                date_col = col; break
        
        if date_col:
            df_csv['Date_Final'] = pd.to_datetime(df_csv[date_col], errors='coerce')
            web_df['Date_Final'] = pd.to_datetime(web_df['Date_Final'], errors='coerce')
            
            # 整合：保留所有原始欄位 (Outer Join)
            final_df = pd.merge(web_df, df_csv, on='Date_Final', how='outer')
            
            # 優先採用 CSV 數據補齊系統欄位
            if 'Close' in final_df.columns:
                final_df['Close'] = final_df['Close'].combine_first(final_df['Close_Web'])
            else:
                final_df['Close'] = final_df['Close_Web']
            
            if 'Vix' in final_df.columns:
                final_df['Vix'] = final_df['Vix'].combine_first(final_df['Vix_Web'])
            else:
                final_df['Vix'] = final_df['Vix_Web']
                
            final_df = final_df.rename(columns={'Date_Final': 'Date'})
        else:
            st.error("❌ CSV 找不到日期欄位，無法對齊。")
            final_df = web_df.rename(columns={'Date_Final': 'Date'})
    else:
        final_df = web_df.rename(columns={'Date_Final': 'Date', 'Close_Web': 'Close', 'Vix_Web': 'Vix'})

    # 排序並移除 Session State 過濾
    st.session_state['merged_df'] = final_df.sort_values('Date')

# ==========================================
# 數據檢查與修正 (修正顯示邏輯)
# ==========================================
if 'merged_df' in st.session_state:
    master = st.session_state['merged_df']
    
    # 偵測缺失值，但顯示時保留所有欄位
    mask = master['Close'].isna() | master['Vix'].isna()
    missing = master[mask]

    if not missing.empty:
        st.warning(f"⚠️ 偵測到有 {len(missing)} 筆數據不全，請修正 Close 與 Vix 欄位：")
        # 這裡會顯示包含你原始因子 (CAPE, Spread等) 的完整表格
        corrected = st.data_editor(missing, num_rows="fixed", use_container_width=True)
        if st.button("💾 儲存修正並繼續"):
            master.update(corrected)
            st.session_state['merged_df'] = master
            st.rerun()
    else:
        st.success("✨ 數據對齊成功！所有因子已就緒。")

    if st.button("🚀 執行全參數深度回測"):
        df_final = master.copy().set_index('Date').ffill().bfill()
        
        # 指標計算
        def calculate_rsi(data, periods=14):
            delta = data.diff(); g = delta.where(delta > 0, 0); l = -delta.where(delta < 0, 0)
            avg_g = g.ewm(com=periods-1, min_periods=periods).mean()
            avg_l = l.ewm(com=periods-1, min_periods=periods).mean()
            return 100 - (100 / (1 + (avg_g / avg_l)))

        df_final['RSI'] = calculate_rsi(df_final['Close'])
        df_final['SMA'] = df_final['Close'].rolling(window=200, min_periods=1).mean()
        df_final['52W_High'] = df_final['Close'].rolling(window=52, min_periods=1).max()
        df_final['Drawdown'] = (df_final['Close'] - df_final['52W_High']) / df_final['52W_High']
        
        # 訊號判定
        df_final['S_Sig'] = (df_final['RSI'] < 45).rolling(window=confirm_w).sum() == confirm_w
        df_final['E_Sig'] = (df_final['RSI'] < 35).rolling(window=confirm_w).sum() == confirm_w
        df_final['M_Sig'] = (df_final['RSI'] < 30).rolling(window=confirm_w).sum() == confirm_w
        
        st.session_state['master'] = df_final[start_d:end_d]
        st.write("### 數據因子與系統指標預覽：")
        st.dataframe(df_final.tail(10)) # 這裡會顯示包含原始因子和計算指標的完整表
