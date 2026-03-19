import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, date

# ==========================================
# 系統初始化 (核心：修復 NameError 與 Date 重複問題)
# ==========================================
st.set_page_config(page_title="矛與盾 7.55 終極修復版", page_icon="🛡️", layout="wide")
st.title("🛡️ 矛與盾 7.55 數據整合系統 ⚔️")

def calculate_perf_metrics(values, initial_capital, dates):
    returns = pd.Series(values).pct_change().dropna()
    total_return = (values[-1] - initial_capital) / initial_capital
    days = (dates.iloc[-1] - dates.iloc[0]).days
    years = days / 365.25 if days > 0 else 1
    cagr = (values[-1] / initial_capital) ** (1 / years) - 1
    std_dev = returns.std() * np.sqrt(52)
    sharpe = cagr / std_dev if std_dev != 0 else 0
    peak = pd.Series(values).cummax()
    mdd = ((pd.Series(values) - peak) / peak).min()
    return {"總報酬率": f"{total_return:.2%}", "年化報酬 (CAGR)": f"{cagr:.2%}", "最大回撤 (MDD)": f"{mdd:.2%}", "年化標準差": f"{std_dev:.2%}", "夏普指數": f"{sharpe:.2f}"}

# ==========================================
# 工具函數：強力因子識別
# ==========================================
def normalize_factors(df):
    """識別並標準化 SP500, SP500EW, VIX, CAPE，保留所有因子"""
    if df.empty: return df
    df = df.reset_index()
    df.columns = [str(c).strip().upper() for c in df.columns]
    
    mapping = {
        'Close': ['SP500', 'VOO', 'CLOSE', 'PRICE', '價格', '收盤'],
        'SP500EW': ['RSP', 'EW', '等權重', 'SP500EW'],
        'Vix': ['VIX', '恐慌', 'CBOE', '^VIX'],
        'Cape': ['CAPE', '席勒', '本益比']
    }
    
    res = pd.DataFrame()
    # 尋找日期
    date_col = next((c for c in df.columns if any(k in c for k in ['DATE', 'TIME', '日期', 'INDEX'])), None)
    if date_col:
        res['Date_Final'] = pd.to_datetime(df[date_col], errors='coerce')
    
    for target, kws in mapping.items():
        for col in df.columns:
            if any(kw in col for kw in kws):
                res[target] = pd.to_numeric(df[col].astype(str).str.replace(',', '').str.replace('$', ''), errors='coerce')
                st.sidebar.success(f"✅ 因子對齊：{col} -> {target}")
                break
    
    # 保留所有原始因子
    for col in df.columns:
        if col not in list(res.columns) + [date_col]:
            res[col] = df[col]
            
    return res.dropna(subset=['Date_Final'])

def get_web_factors(start, end):
    """抓取聯網基準，修復 NameError Typos"""
    with st.spinner("聯網校準 SP500、等權重與 VIX..."):
        spy = yf.Ticker("SPY").history(start=start, end=end, interval="1wk")
        voo = yf.Ticker("VOO").history(start=start, end=end, interval="1wk")
        rsp = yf.Ticker("RSP").history(start=start, end=end, interval="1wk")
        vix = yf.Ticker("^VIX").history(start=start, end=end, interval="1wk")
        
        for d in [spy, voo, rsp, vix]:
            if not d.empty: d.index = d.index.tz_localize(None)
            
        if voo.empty:
            full_voo = spy[['Close']] * 0.9 
        else:
            first_voo = voo.index[0]
            # 【修復重點】將原本錯誤的 first_v 改為 first_voo
            ratio = voo.at[first_voo, 'Close'] / spy.at[first_voo, 'Close'] if first_voo in spy.index else 0.9
            full_voo = pd.concat([spy[:first_voo].iloc[:-1][['Close']] * ratio, voo[['Close']]])
            
        web_df = pd.DataFrame(index=spy.index)
        web_df['Close_Web'] = full_voo['Close']
        web_df['SP500EW_Web'] = rsp['Close']
        web_df['Vix_Web'] = vix['Close']
        web_df.index.name = 'Date_Final'
        return web_df.reset_index()

# ==========================================
# 主邏輯
# ==========================================
st.sidebar.header("📊 系統控制")
start_d = st.sidebar.date_input("回測起始日", date(2003, 5, 1))
end_d = st.sidebar.date_input("回測結束日", date.today())
init_total = st.sidebar.number_input("初始總資金 (NTD)", value=9000000)
base_dca = st.sidebar.number_input("每月 DCA 基數", value=200000)
confirm_w = st.sidebar.slider("訊號連續週數確認", 1, 5, 1)

up_file = st.sidebar.file_uploader("📥 上傳 CSV 數據", type=['csv'])

if st.sidebar.button("🔄 執行全因子強力整合", type="primary"):
    web_data = get_web_factors(start_d, end_d)
    
    if up_file:
        df_csv = normalize_factors(pd.read_csv(up_file))
        df_csv['Date_Final'] = pd.to_datetime(df_csv['Date_Final'])
        web_data['Date_Final'] = pd.to_datetime(web_data['Date_Final'])
        
        # 【修復重點】移除 CSV 中可能存在的舊 'Date' 欄位，避免合併後出現重複 Date 標籤
        if 'DATE' in df_csv.columns: df_csv = df_csv.drop(columns=['DATE'])
        
        final = pd.merge(web_data, df_csv, on='Date_Final', how='outer')
        
        for f in ['Close', 'SP500EW', 'Vix']:
            web_col = f"{f}_Web" if f != 'SP500EW' else "SP500EW_Web"
            if f not in final.columns: final[f] = final[web_col]
            else: final[f] = final[f].combine_first(final[web_col])
        
        final = final.drop(columns=['Close_Web', 'SP500EW_Web', 'Vix_Web'])
        final = final.rename(columns={'Date_Final': 'Date'})
    else:
        final = web_data.rename(columns={'Date_Final': 'Date', 'Close_Web': 'Close', 'SP500EW_Web': 'SP500EW', 'Vix_Web': 'Vix'})

    if 'Date' in final.columns:
        # 確保 Date 標籤唯一且已排序
        final = final.loc[:, ~final.columns.duplicated()].sort_values('Date').dropna(subset=['Date'])
        st.session_state['merged_df'] = final
    else:
        st.error("❌ 無法建立日期標籤，請檢查 CSV 格式。")

# ==========================================
# 補強與回測
# ==========================================
if 'merged_df' in st.session_state:
    master = st.session_state['merged_df']
    key_factors = ['Close', 'SP500EW', 'Vix', 'Cape']
    present = [f for f in key_factors if f in master.columns]
    mask = master[present].isna().any(axis=1)
    missing = master[mask]

    if not missing.empty:
        st.warning(f"⚠️ 偵測到 {len(missing)} 筆數據缺失，請在此補齊：")
        corrected = st.data_editor(missing, num_rows="fixed", use_container_width=True)
        if st.button("💾 儲存並執行深度分析"):
            master.update(corrected)
            st.session_state['merged_df'] = master
            st.rerun()
    else:
        st.success("✨ 四大因子已完整對齊！")

    if st.button("🚀 執行量化策略回測"):
        df_f = master.copy().set_index('Date').ffill().bfill()
        
        def get_rsi(s, p=14):
            d = s.diff(); g = d.where(d > 0, 0); l = -d.where(d < 0, 0)
            ag = g.ewm(com=p-1, min_periods=p).mean(); al = l.ewm(com=p-1, min_periods=p).mean()
            return 100 - (100 / (1 + (ag / (al + 1e-9))))

        df_f['RSI'] = get_rsi(df_f['Close'])
        df_f['SMA_200'] = df_f['Close'].rolling(window=200, min_periods=1).mean()
        df_f['DD'] = (df_f['Close'] - df_f['Close'].rolling(window=52, min_periods=1).max()) / df_f['Close'].rolling(window=52, min_periods=1).max()
        
        st.session_state['master'] = df_f[start_d:end_d]
        st.write("### 終極因子數據預覽：")
        cols = ['Close', 'SP500EW', 'Vix', 'Cape', 'RSI', 'DD'] + [c for c in df_f.columns if c not in ['Close', 'SP500EW', 'Vix', 'Cape', 'RSI', 'DD']]
        st.dataframe(df_f[cols].tail(10))
