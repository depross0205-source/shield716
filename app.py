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
st.set_page_config(page_title="矛與盾 7.42 強力對齊版", page_icon="🛡️", layout="wide")
st.title("🛡️ 矛與盾 7.42 數據強力對齊系統 ⚔️")

# ==========================================
# 工具函數：數據標準化
# ==========================================
def normalize_columns(df):
    """【全能補強】無視大小寫、空格、索引，強制抓取價格與 VIX"""
    if df.empty: return df
    
    # 1. 先將隱藏在索引裡的日期或價格釋放出來
    df = df.reset_index()
    
    # 2. 清理所有欄位名稱：去空格、全部轉大寫
    df.columns = [str(c).strip().upper() for c in df.columns]
    
    # 3. 定義模糊匹配關鍵字
    price_kws = ['CLOSE', 'PRICE', 'VOO', 'SPY', 'SP500', '價格', '收盤', '收盤價', 'VALUE']
    vix_kws = ['VIX', '恐慌', 'CBOE', '^VIX']
    
    # 4. 強力搜尋價格欄位
    target_price = None
    for col in df.columns:
        if any(kw in col for kw in price_kws):
            target_price = col
            break
            
    if target_price:
        # 處理數字格式 (移除逗號和貨幣符號，避免轉型失敗變 None)
        df['Close'] = df[target_price].astype(str).str.replace(',', '').str.replace('$', '').str.strip()
        df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
        st.sidebar.info(f"✅ 已偵測到價格欄位：{target_price}")
    
    # 5. 強力搜尋 VIX 欄位
    target_vix = None
    for col in df.columns:
        if any(kw in col for kw in vix_kws):
            target_vix = col
            break
            
    if target_vix:
        df['Vix'] = pd.to_numeric(df[target_vix].astype(str).str.replace(',', ''), errors='coerce')
        st.sidebar.info(f"✅ 已偵測到 VIX 欄位：{target_vix}")
    else:
        df['Vix'] = np.nan # 留空讓後續手動補齊
        
    return df

def get_base_data(start, end):
    """聯網備援：2003年起 SPY/VOO 數據"""
    with st.spinner("正在聯網獲取 VOO/SPY/VIX 數據作為基準..."):
        spy = yf.Ticker("SPY").history(start=start, end=end, interval="1wk")
        voo = yf.Ticker("VOO").history(start=start, end=end, interval="1wk")
        vix = yf.Ticker("^VIX").history(start=start, end=end, interval="1wk")
        
        spy.index = spy.index.tz_localize(None); voo.index = voo.index.tz_localize(None); vix.index = vix.index.tz_localize(None)
        
        # 2010 年前 VOO 未上市，用 SPY 等比例換算
        if voo.empty:
            full_voo = spy[['Close']] * 0.9 
        else:
            first_v = voo.index[0]
            if first_v in spy.index:
                ratio = voo.at[first_v, 'Close'] / spy.at[first_v, 'Close']
                pre_v = spy[:first_v].iloc[:-1][['Close']] * ratio
                full_voo = pd.concat([pre_v, voo[['Close']]])
            else:
                full_voo = voo[['Close']]
        
        df = pd.DataFrame(index=spy.index)
        df['Close'] = full_voo['Close']
        df['Vix'] = vix['Close']
        return df

# ==========================================
# 主邏輯執行
# ==========================================
st.sidebar.header("📊 系統控制")
start_d = st.sidebar.date_input("回測起始日", date(2003, 5, 1))
end_d = st.sidebar.date_input("回測結束日", date.today())
init_core = st.sidebar.number_input("核心初始資金", value=8000000)
init_rsv = st.sidebar.number_input("預備金總額", value=1000000)
base_dca = st.sidebar.number_input("基礎月扣額", value=200000)

up_file = st.sidebar.file_uploader("📥 上傳 CSV 數據", type=['csv'])

if st.sidebar.button("🔄 執行數據強力整合", type="primary"):
    # 1. 聯網數據 (底稿)
    web_df = get_base_data(start_d, end_d)
    web_df = web_df.reset_index().rename(columns={'Date': 'Date_Web'})
    
    # 2. 處理 CSV 數據
    if up_file:
        # 自動偵測分隔符號 (防止 Tab 或分號造成讀取失敗)
        df_csv = pd.read_csv(up_file, index_col=None, sep=None, engine='python')
        df_csv = normalize_columns(df_csv)
        
        # 尋找日期欄位進行對齊
        date_col = None
        for col in df_csv.columns:
            if any(kw in str(col).upper() for kw in ['DATE', 'TIME', '日期', '時間']):
                date_col = col; break
        
        if date_col:
            df_csv['Date_Final'] = pd.to_datetime(df_csv[date_col], errors='coerce')
            web_df['Date_Final'] = pd.to_datetime(web_df['Date_Web'], errors='coerce')
            
            # 拼接：以 Web 的日期為準，填入 CSV 的 Close
            final_df = pd.merge(web_df, df_csv, on='Date_Final', how='left', suffixes=('_web', '_csv'))
            # 優先採用 CSV 的數據，若無則用 Web
            final_df['Close'] = final_df['Close_csv'].combine_first(final_df['Close_web'])
            final_df['Vix'] = final_df['Vix_csv'].combine_first(final_df['Vix_web'])
            final_df = final_df.rename(columns={'Date_Final': 'Date'})
        else:
            st.error("❌ CSV 找不到日期欄位！")
            final_df = web_df.rename(columns={'Date_Web': 'Date'})
    else:
        final_df = web_df.rename(columns={'Date_Web': 'Date'})

    st.session_state['merged_df'] = final_df[['Date', 'Close', 'Vix']].sort_values('Date')

# ==========================================
# 數據修正與回測 (僅顯示缺失)
# ==========================================
if 'merged_df' in st.session_state:
    master = st.session_state['merged_df']
    mask = master['Close'].isna() | master['Vix'].isna()
    missing = master[mask]

    if not missing.empty:
        st.warning(f"⚠️ 仍有 {len(missing)} 筆數據缺失，請在下方表格直接輸入修正：")
        corrected = st.data_editor(missing, num_rows="fixed", use_container_width=True, key="fix_742")
        if st.button("💾 儲存並執行回測"):
            master.update(corrected)
            st.session_state['merged_df'] = master
            st.rerun()
    else:
        st.success("✨ 數據對齊成功！")

    if st.button("🚀 開始深度回測"):
        # (指標計算與圖表邏輯同前，確保 Close 欄位被引用)
        df_final = master.copy().set_index('Date').ffill().bfill()
        # ... [其餘指標計算代碼] ...
        st.write("數據預覽：")
        st.table(df_final.tail(5))
