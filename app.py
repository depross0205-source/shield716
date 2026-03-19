import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, date

# ==========================================
# 1. 系統環境與相容性 (信心程度：10 分)
# ==========================================
st.set_page_config(page_title="矛與盾 8.50 終極版", page_icon="🛡️", layout="wide")
st.title("🛡️ 矛與盾 8.50 核心邏輯補強系統 ⚔️")

def safe_divider():
    """相容 Streamlit 1.19.0 版本"""
    try: st.divider()
    except: st.markdown("---")

# ==========================================
# 2. 數據清洗與因子強力對齊
# ==========================================
def normalize_factors(df):
    """識別核心因子並保留原始數據，Close 強制同步 SP500"""
    if df.empty: return df
    df = df.reset_index()
    # 統一清理欄位名：去空格、轉大寫
    df.columns = [str(c).strip().upper() for c in df.columns]
    
    mapping = {
        'SP500': ['SP500', 'VOO', 'PRICE', '價格', '收盤', 'CLOSE'],
        'SP500EW': ['RSP', 'EW', '等權重', 'SP500EW'],
        'HY_SPREAD': ['SPREAD', 'HY_SPREAD', '利差'],
        'TIPS_10Y': ['TIPS', 'TIPS_10Y', '實質利率'],
        'VIX': ['VIX', '恐慌', '^VIX'],
        'CAPE': ['CAPE', '席勒', '本益比']
    }
    
    res = pd.DataFrame()
    # 尋找唯一的日期欄位，並強制轉換
    date_col = next((c for c in df.columns if any(k in c for k in ['DATE', 'TIME', '日期', 'INDEX'])), None)
    if date_col:
        res['Date_Final'] = pd.to_datetime(df[date_col], errors='coerce')
    
    # 核心因子識別與數值化
    for target_key, kws in mapping.items():
        for col in df.columns:
            if any(kw in col for kw in kws) and target_key not in res.columns:
                res[target_key] = pd.to_numeric(df[col].astype(str).str.replace(',', '').str.replace('$', ''), errors='coerce')
                break
    
    # 【需求實作】Close 參照 SP500 數字貼上，確保兩者同步
    if 'SP500' in res.columns: 
        res['Close'] = res['SP500']
    
    # 保留所有其餘因子欄位 (如 Spread, TIPS 等)
    for col in df.columns:
        if col not in list(res.columns) + [date_col]:
            res[col] = df[col]
            
    return res.dropna(subset=['Date_Final'])

def get_web_patch(start_d, end_d):
    """獲取聯網最新數據作為時間軸補強"""
    try:
        spy = yf.Ticker("SPY").history(start=start_d, end=end_d, interval="1wk")
        rsp = yf.Ticker("RSP").history(start=start_d, end=end_d, interval="1wk")
        vix = yf.Ticker("^VIX").history(start=start_d, end=end_d, interval="1wk")
        for d in [spy, rsp, vix]:
            if not d.empty: d.index = d.index.tz_localize(None)
        
        web_df = pd.DataFrame(index=spy.index)
        web_df['SP500_Web'] = spy['Close'] * 0.9 # 換算 VOO 等級
        web_df['SP500EW_Web'] = rsp['Close']
        web_df['VIX_Web'] = vix['Close']
        web_df.index.name = 'Date_Final'
        return web_df.reset_index()
    except:
        return pd.DataFrame()

# ==========================================
# 3. 側邊欄：1000 萬資產配置與策略參數
# ==========================================
st.sidebar.header("💰 1. 1000 萬資金架構")
TOTAL_CAP = st.sidebar.number_input("總資產額度 (NTD)", value=10000000)
CASH_RSV = st.sidebar.number_input("現金預備金 (200萬)", value=2000000)
DCA_POOL = TOTAL_CAP - CASH_RSV # 剩餘 800 萬用於 DCA 池

BASE_DCA = st.sidebar.number_input("基礎月扣基數", value=200000)

st.sidebar.header("🛡️ 2. 自定義熔斷機制")
with st.sidebar.expander("熔斷門檻設定", expanded=True):
    M_LOSS = st.slider("虧損熔斷門檻 (%)", -30, -5, -15) / 100
    M_SMA = st.number_input("參考均線週期 (週)", value=200)
    M_VIX = st.slider("VIX 恐慌熔斷點", 20, 60, 40)

st.sidebar.header("⚙️ 3. RSI 買進訊號")
RSI_P = st.sidebar.number_input("RSI 計算週期", value=14)
CONF_W = st.sidebar.slider("連續訊號確認週數", 1, 5, 1)

with st.sidebar.expander("加碼階梯設定"):
    R_SPEED = st.slider("加速 (2x) RSI", 30, 55, 45)
    R_EXTRA = st.slider("爆買 (4x) RSI", 20, 45, 35)
    R_MELT_B = st.slider("熔斷中補丁 RSI", 10, 40, 30)

up_file = st.sidebar.file_uploader("📥 4. 上傳 CSV 資料庫 (優先採用)", type=['csv'])

# ==========================================
# 4. 數據整合流程 (徹底解決 Date 重複與 NameError)
# ==========================================
if st.sidebar.button("🚀 執行全因子整合與量化分析", type="primary"):
    web_df = get_web_patch(date(2003, 5, 1), date.today())
    
    if up_file:
        df_csv = normalize_factors(pd.read_csv(up_file))
        # 【關鍵修復】移除重複標籤，解決 ValueError
        df_csv = df_csv.loc[:, ~df_csv.columns.duplicated()].drop_duplicates(subset=['Date_Final'])
        web_df = web_df.drop_duplicates(subset=['Date_Final'])
        
        # 進行外部對齊合併
        final = pd.merge(web_df, df_csv, on='Date_Final', how='outer')
        
        # 【關鍵修復】修正 NameError: target
        for f in ['SP500', 'SP500EW', 'VIX']:
            web_c = f"{f}_Web" if f != 'VIX' else "VIX_Web"
            if web_c in final.columns:
                if f not in final.columns: final[f] = final[web_c]
                else: final[f] = final[f].combine_first(final[web_c])
        
        final['Close'] = final['SP500']
        # 清除 Web 暫存欄位並重命名唯一日期標籤
        final = final.drop(columns=[c for c in final.columns if '_Web' in c]).rename(columns={'Date_Final': 'Date'})
    else:
        final = web_df.rename(columns={'Date_Final': 'Date', 'SP500_Web': 'SP500', 'SP500_
