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
st.set_page_config(page_title="矛與盾 7.40 數據強制對齊版", page_icon="🛡️", layout="wide")
st.title("🛡️ 矛與盾 7.40 數據強制對齊系統 ⚔️")

# ==========================================
# 工具函數：績效計算
# ==========================================
def calculate_perf_metrics(values, initial_capital, dates):
    """
    [span_0](start_span)計算量化指標[span_0](end_span)
    - CAGR: (Ending/Beginning)^(1/years) - 1
    - Sharpe: CAGR / Std_Dev
    """
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

def normalize_columns(df):
    """【強力修復】確保 Price 正確對應到 Close"""
    if df.empty: return df
    
    # 1. 清理欄位名稱：去空格、轉小寫進行比對
    df.columns = df.columns.str.strip()
    col_map = {c.lower(): c for c in df.columns}
    
    # 2. 定義優先順序：只要匹配到這些關鍵字，就認定它是價格
    target_col = None
    for key in ['price', 'close', 'voo', 'spy', '收盤', '價格']:
        if key in col_map:
            target_col = col_map[key]
            break
            
    # 3. 強制賦值：將找到的欄位內容複製到系統統一的 'Close' 欄位
    if target_col:
        df['Close'] = pd.to_numeric(df[target_col], errors='coerce')
    
    # 4. 對 VIX 執行同樣邏輯
    for key in ['vix', '恐慌', '^vix']:
        if key in col_map:
            df['Vix'] = pd.to_numeric(df[col_map[key]], errors='coerce')
            break
    
    # 若 Vix 還是空的，給予預設值防崩潰，並執行自動填補
    if 'Vix' not in df.columns: df['Vix'] = np.nan
    df = df.ffill().bfill()
    return df

def get_base_data(start, end):
    with st.spinner("正在聯網校準 2003 年起之 VOO/SPY 數據..."):
        spy = yf.Ticker("SPY").history(start=start, end=end, interval="1wk")
        voo = yf.Ticker("VOO").history(start=start, end=end, interval="1wk")
        vix = yf.Ticker("^VIX").history(start=start, end=end, interval="1wk")
        
        spy.index = spy.index.tz_localize(None); voo.index = voo.index.tz_localize(None); vix.index = vix.index.tz_localize(None)
        
        # 2010 年前用 SPY 換算 VOO
        if voo.empty:
            full_voo = spy[['Close']] * 0.9 
        else:
            first_date = voo.index[0]
            if first_date in spy.index:
                ratio = voo.at[first_date, 'Close'] / spy.at[first_date, 'Close']
                pre_voo = spy[:first_date].iloc[:-1][['Close']] * ratio
                full_voo = pd.concat([pre_voo, voo[['Close']]])
            else:
                full_voo = voo[['Close']]
        
        df = pd.DataFrame(index=spy.index)
        df['Close'] = full_voo['Close']
        df['Vix'] = vix['Close']
        return normalize_columns(df)

# ==========================================
# 介面與邏輯執行
# ==========================================
st.sidebar.header("📊 參數設定")
start_d = st.sidebar.date_input("起始日", date(2003, 5, 1))
end_d = st.sidebar.date_input("結束日", date.today())
init_core = st.sidebar.number_input("核心初始資金", value=8000000)
init_rsv = st.sidebar.number_input("預備金總額", value=1000000)
base_dca = st.sidebar.number_input("基礎每月 DCA", value=200000)
confirm_w = st.sidebar.slider("訊號連續週數確認", 1, 5, 1)

up_file = st.sidebar.file_uploader("📥 上傳 CSV 數據", type=['csv'])

if st.sidebar.button("🔄 執行數據整合 (強力對齊版)", type="primary"):
    # 1. 聯網數據
    web_df = get_base_data(start_d, end_d)
    
    # 2. CSV 數據
    if up_file:
        df_csv = pd.read_csv(up_file, index_col=0, parse_dates=True)
        df_csv.index = df_csv.index.tz_localize(None)
        df_csv = normalize_columns(df_csv)
        # 拼接：CSV 的資料優先，避免被 Web 資料覆蓋掉你辛苦整理的部分
        final_merged = pd.concat([df_csv, web_df])
        final_merged = final_merged[~final_merged.index.duplicated(keep='first')]
    else:
        final_merged = web_df

    st.session_state['merged_df'] = final_merged.sort_index().reset_index()

if 'merged_df' in st.session_state:
    master_df = st.session_state['merged_df']
    # 只找出 Close 或 Vix 有缺失的行
    mask = master_df['Close'].isna() | master_df['Vix'].isna()
    missing = master_df[mask]

    if not missing.empty:
        st.warning(f"⚠️ 偵測到有 {len(missing)} 筆數據不全，請在此補齊 (日期: {missing['Date'].min().date()} 起)：")
        # 這裡會顯示讓你可以直接改數據的表格
        corrected = st.data_editor(missing, num_rows="fixed", use_container_width=True, key="fix_740")
        if st.button("💾 儲存修正並執行"):
            master_df.update(corrected)
            st.session_state['merged_df'] = master_df
            st.rerun()
    else:
        st.success("✨ 資料對齊成功，Close 與 Vix 均有數據。")

    if st.button("🚀 開始深度回測"):
        df_final = master_df.copy()
        df_final['Date'] = pd.to_datetime(df_final['Date'])
        df_final = df_final.set_index('Date').ffill().bfill()
        
        # 指標計算
        def calculate_rsi(data, periods=14):
            delta = data.diff(); g = (delta.where(delta > 0, 0)).fillna(0); l = (-delta.where(delta < 0, 0)).fillna(0)
            avg_g = g.ewm(com=periods-1, min_periods=periods).mean(); avg_l = l.ewm(com=periods-1, min_periods=periods).mean()
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

# --- 以下為績效呈現 (略，邏輯同前) ---
if 'master' in st.session_state:
    data = st.session_state['master']
    st.write("### 數據最後 5 筆預覽 (檢查 Close 欄位)")
    st.table(data[['Close', 'Vix', 'RSI', 'Drawdown']].tail(5))
    # ... (其餘回測與圖表代碼)
