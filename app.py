import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, date

# ==========================================
# 系統初始化 (解決版本不相容問題)
# ==========================================
st.set_page_config(page_title="矛與盾 7.65 終極版", page_icon="🛡️", layout="wide")
st.title("🛡️ 矛與盾 7.65 終極量化整合系統 ⚔️")

# 解決舊版 Streamlit 不支援 divider 的問題
def safe_divider():
    try: st.divider()
    except AttributeError: st.markdown("---")

# ==========================================
# 工具函數：強力因子識別與標準化
# ==========================================
def normalize_factors(df):
    """【需求 1 & 4】識別因子並保留所有原始數據，Close 參照 SP500"""
    if df.empty: return df
    df = df.reset_index()
    # 清理欄位名
    df.columns = [str(c).strip().upper() for c in df.columns]
    
    mapping = {
        'SP500': ['SP500', 'VOO', 'PRICE', '價格', '收盤價', 'CLOSE'],
        'SP500EW': ['RSP', 'EW', '等權重', 'SP500EW'],
        'HY_Spread': ['SPREAD', 'HY_SPREAD', '利差'],
        'TIPS_10Y': ['TIPS', 'TIPS_10Y', '實質利率'],
        'Vix': ['VIX', '恐慌', '^VIX'],
        'Cape': ['CAPE', '席勒', '本益比']
    }
    
    res = pd.DataFrame()
    # 尋找日期並強制轉換
    date_col = next((c for c in df.columns if any(k in c for k in ['DATE', 'TIME', '日期', 'INDEX'])), None)
    if date_col:
        res['Date_Final'] = pd.to_datetime(df[date_col], errors='coerce')
    
    # 識別核心因子
    for target, kws in mapping.items():
        for col in df.columns:
            if any(kw in col for kw in kws) and target not in res.columns:
                res[target] = pd.to_numeric(df[col].astype(str).str.replace(',', '').str.replace('$', ''), errors='coerce')
                break
    
    # 【核心需求】Close 參照 SP500 數字貼上，而不是替代
    if 'SP500' in res.columns:
        res['Close'] = res['SP500']
    
    # 保留所有其餘欄位
    for col in df.columns:
        if col not in list(res.columns) + [date_col]:
            res[col] = df[col]
            
    return res.dropna(subset=['Date_Final'])

def get_web_data(start_date, end_date):
    """【修復 TypeError】聯網獲取最新基準數據"""
    spy = yf.Ticker("SPY").history(start=start_date, end=end_date, interval="1wk")
    rsp = yf.Ticker("RSP").history(start=start_date, end=end_date, interval="1wk")
    vix = yf.Ticker("^VIX").history(start=start_date, end=end_date, interval="1wk")
    
    for d in [spy, rsp, vix]:
        if not d.empty: d.index = d.index.tz_localize(None)
            
    web_df = pd.DataFrame(index=spy.index)
    web_df['SP500_Web'] = spy['Close'] * 0.9 # 模擬 VOO
    web_df['SP500EW_Web'] = rsp['Close']
    web_df['Vix_Web'] = vix['Close']
    web_df.index.name = 'Date_Final'
    return web_df.reset_index()

# ==========================================
# 側邊欄：【需求 2 & 3】參數與 1000 萬資金邏輯
# ==========================================
st.sidebar.header("💰 1. 資金配置中心 (1000萬)")
total_funds = st.sidebar.number_input("總投資資金 (NTD)", value=10000000)
cash_reserve = st.sidebar.number_input("現金預備金 (抄底用)", value=2000000)
dca_pool = total_funds - cash_reserve # 剩餘可用於 DCA
st.sidebar.info(f"剩餘 DCA 可用資金：{dca_pool/10000:.0f} 萬")

base_dca_amt = st.sidebar.number_input("每月 DCA 基礎基數 (NTD)", value=200000)

st.sidebar.header("⚙️ 2. 策略規則調整")
rsi_p = st.sidebar.number_input("RSI 計算週期 (週)", value=14)
confirm_w = st.sidebar.slider("訊號連續確認週數", 1, 5, 1)

with st.sidebar.expander("RSI 觸發門檻設定", expanded=True):
    rsi_speed = st.slider("提速扣款 (2倍) 門檻", 30, 55, 45)
    rsi_extra = st.slider("超賣加碼 (40萬) 門檻", 20, 45, 35)
    rsi_melt_buy = st.slider("熔斷中允許買入門檻", 10, 40, 30)

up_file = st.sidebar.file_uploader("📥 3. 上傳 CSV 資料庫 (優先採用)", type=['csv'])

# ==========================================
# 數據整合引擎：【需求 4】CSV -> 聯網 -> 前週沿用
# ==========================================
if st.sidebar.button("🚀 執行全數據強力整合", type="primary"):
    # 1. 獲取聯網數據作為最新日期補充
    web_df = get_web_data(date(2003, 5, 1), date.today())
    
    if up_file:
        df_csv = normalize_factors(pd.read_csv(up_file))
        # 確保日期對齊
        df_csv['Date_Final'] = pd.to_datetime(df_csv['Date_Final'])
        web_df['Date_Final'] = pd.to_datetime(web_df['Date_Final'])
        
        # 整合：Outer Join 保留所有日期與原始因子
        final = pd.merge(web_df, df_csv, on='Date_Final', how='outer')
        
        # 補位：優先用 CSV 數據，CSV 沒數據的部分由 Web 補入
        for f in ['SP500', 'SP500EW', 'Vix']:
            web_col = f"{f}_Web"
            if f not in final.columns: final[f] = final[web_col]
            else: final[f] = final[f].combine_first(final[web_col])
        
        # 強制 Close 同步自 SP500 欄位
        final['Close'] = final['SP500']
        final = final.drop(columns=['SP500_Web', 'SP500EW_Web', 'Vix_Web'])
        final = final.rename(columns={'Date_Final': 'Date'})
    else:
        final = web_df.rename(columns={'Date_Final': 'Date', 'SP500_Web': 'SP500', 'SP500_Web': 'Close', 'SP500EW_Web': 'SP500EW', 'Vix_Web': 'Vix'})

    # 【需求 4】一律沿用前一週數據 (ffill) 並移除重複欄位
    final = final.loc[:, ~final.columns.duplicated()].sort_values('Date').ffill().dropna(subset=['Date', 'Close'])
    st.session_state['merged_df'] = final

# ==========================================
# 補強與回測介面
# ==========================================
if 'merged_df' in st.session_state:
    master = st.session_state['merged_df']
    factors = ['Close', 'SP500', 'SP500EW', 'HY_Spread', 'TIPS_10Y', 'Vix', 'Cape']
    present = [f for f in factors if f in master.columns]
    mask = master[present].isna().any(axis=1)
    missing = master[mask]

    if not missing.empty:
        st.warning(f"⚠️ 偵測到 {len(missing)} 筆核心因子缺失，請補齊或系統將持續 ffill：")
        corrected = st.data_editor(missing, num_rows="fixed", use_container_width=True)
        if st.button("💾 儲存並執行深度分析"):
            master.update(corrected)
            st.session_state['merged_df'] = master.ffill()
            st.rerun()
    else:
        st.success("✨ 所有因子數據已就緒。")

    if st.button("🚀 執行量化回測"):
        df_f = master.copy().set_index('Date').ffill()
        
        # 指標計算邏輯
        def get_rsi(s, p=14):
            d = s.diff(); g = d.where(d > 0, 0); l = -d.where(d < 0, 0)
            ag = g.ewm(com=p-1, min_periods=p).mean(); al = l.ewm(com=p-1, min_periods=p).mean()
            return 100 - (100 / (1 + (ag / (al + 1e-9))))

        df_f['RSI'] = get_rsi(df_f['Close'], rsi_p)
        df_f['SMA_200'] = df_f['Close'].rolling(window=200, min_periods=1).mean()
        df_f['DD'] = (df_f['Close'] - df_f['Close'].rolling(window=52, min_periods=1).max()) / df_f['Close'].rolling(window=52, min_periods=1).max()
        
        # 訊號確認
        df_f['S_Sig'] = (df_f['RSI'] < rsi_speed).rolling(window=confirm_w).sum() == confirm_w
        df_f['E_Sig'] = (df_f['RSI'] < rsi_extra).rolling(window=confirm_w).sum() == confirm_w
        df_f['M_Sig'] = (df_f['RSI'] < rsi_melt_buy).rolling(window=confirm_w).sum() == confirm_w
        
        st.session_state['master'] = df_f
        st.write("### 數據全因子預覽 (含前週沿用結果)：")
        cols_display = ['Close', 'SP500EW', 'HY_Spread', 'TIPS_10Y', 'Vix', 'Cape', 'RSI', 'DD']
        st.dataframe(df_f[[c for c in cols_display if c in df_f.columns]].tail(10))
