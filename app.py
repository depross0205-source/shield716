import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, date

# ==========================================
# 系統初始化 (根據 2026-03-15 規則執行)
# ==========================================
st.set_page_config(page_title="矛與盾 7.35 數據補強版", page_icon="🛡️", layout="wide")
st.title("🛡️ 矛與盾 7.35 精準補強系統 ⚔️")

# ==========================================
# 工具函數：技術指標與績效計算
# ==========================================
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
    return {
        "總報酬率": f"{total_return:.2%}",
        "年化報酬 (CAGR)": f"{cagr:.2%}",
        "最大回撤 (MDD)": f"{mdd:.2%}",
        "年化標準差": f"{std_dev:.2%}",
        "夏普指數": f"{sharpe:.2f}"
    }

def normalize_columns(df):
    """欄位強制對等：Price 直接等於 Close，並執行自動補償"""
    if df.empty: return df
    df.columns = [str(c).capitalize() for c in df.columns]
    
    # 【需求 1】直接讓 Close 等於 Price
    if 'Price' in df.columns:
        df['Close'] = df['Price']
    
    # 執行自動補償 (ffill)
    df = df.ffill()
    return df

def get_base_data(start, end):
    with st.spinner("正在聯網獲取 VOO/SPY/VIX 數據..."):
        spy = yf.Ticker("SPY").history(start=start, end=end, interval="1wk")
        voo = yf.Ticker("VOO").history(start=start, end=end, interval="1wk")
        vix = yf.Ticker("^VIX").history(start=start, end=end, interval="1wk")
        
        spy.index = spy.index.tz_localize(None); voo.index = voo.index.tz_localize(None); vix.index = vix.index.tz_localize(None)
        
        if voo.empty:
            full_voo = spy[['Close']] * 0.9 
        else:
            ratio = voo['Close'].iloc[0] / spy.loc[voo.index[0], 'Close']
            pre_voo = spy[:voo.index[0]].iloc[:-1][['Close']] * ratio
            full_voo = pd.concat([pre_voo, voo[['Close']]])
        
        df = pd.DataFrame({'Close': full_voo['Close'], 'Vix': vix['Close']})
        return normalize_columns(df)

def calculate_rsi(data, periods=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)
    avg_gain = gain.ewm(com=periods - 1, min_periods=periods).mean()
    avg_loss = loss.ewm(com=periods - 1, min_periods=periods).mean()
    return 100 - (100 / (1 + (avg_gain / avg_loss)))

# ==========================================
# 側邊欄：參數設定
# ==========================================
st.sidebar.header("📅 1. 區間與資金")
start_d = st.sidebar.date_input("起始日", date(2003, 5, 1))
end_d = st.sidebar.date_input("結束日", date.today())
init_core = st.sidebar.number_input("核心初始資金", value=8000000)
init_rsv = st.sidebar.number_input("預備金總額", value=1000000)
base_dca = st.sidebar.number_input("基礎每月 DCA", value=200000)

st.sidebar.header("⚙️ 2. 訊號參數")
rsi_p = st.sidebar.number_input("RSI 週期", value=14)
confirm_w = st.sidebar.slider("連續週數確認", 1, 5, 1)

with st.sidebar.expander("🔍 RSI 門檻設定"):
    rsi_speed = st.slider("提速門檻 (40萬)", 30, 55, 45)
    rsi_extra = st.slider("加碼門檻 (80萬)", 20, 45, 35)
    rsi_melt_buy = st.slider("熔斷加碼門檻", 10, 40, 30)

up_file = st.sidebar.file_uploader("📥 3. 上傳 CSV", type=['csv'])

# ==========================================
# 數據整合流程
# ==========================================
if st.sidebar.button("🔄 執行數據整合", type="primary"):
    base_df = get_base_data(start_d, end_d)
    if up_file:
        df_csv = pd.read_csv(up_file, index_col=0, parse_dates=True)
        df_csv.index = df_csv.index.tz_localize(None)
        df_csv = normalize_columns(df_csv)
        base_df = pd.concat([df_csv, base_df])
        base_df = base_df[~base_df.index.duplicated(keep='last')]
    
    st.session_state['merged_df'] = base_df.sort_index().reset_index()

# ==========================================
# 【需求 2】僅顯示缺漏資料的表格
# ==========================================
if 'merged_df' in st.session_state:
    master_df = st.session_state['merged_df']
    # 偵測哪些行有缺漏 (Close 或 Vix 為 NaN)
    mask = master_df['Close'].isna() | master_df['Vix'].isna()
    missing_data = master_df[mask]

    if not missing_data.empty:
        st.warning(f"⚠️ 偵測到有 {len(missing_data)} 筆數據不全，請在此補齊：")
        corrected_rows = st.data_editor(
            missing_data,
            num_rows="fixed",
            use_container_width=True,
            key="missing_editor"
        )
        
        if st.button("💾 儲存修正並執行回測"):
            # 將修正後的資料填回主表格
            master_df.update(corrected_rows)
            st.session_state['merged_df'] = master_df
            st.success("✅ 修正已套用，即將執行分析。")
            st.rerun()
    else:
        st.success("✨ 數據完整，無需手動補齊。")

    if st.button("🚀 開始深度回測"):
        final_df = master_df.copy()
        final_df['Date'] = pd.to_datetime(final_df['Date'])
        final_df = final_df.set_index('Date').tz_localize(None)
        
        # 指標運算
        final_df['RSI'] = calculate_rsi(final_df['Close'], periods=rsi_p)
        final_df['SMA'] = final_df['Close'].rolling(window=200, min_periods=1).mean()
        final_df['52W_High'] = final_df['Close'].rolling(window=52, min_periods=1).max()
        final_df['Drawdown'] = (final_df['Close'] - final_df['52W_High']) / final_df['52W_High']
        
        # 訊號判定 (連續週數)
        final_df['Speed_Sig'] = (final_df['RSI'] < rsi_speed).rolling(window=confirm_w).sum() == confirm_w
        final_df['Extra_Sig'] = (final_df['RSI'] < rsi_extra).rolling(window=confirm_w).sum() == confirm_w
        final_df['Melt_Sig'] = (final_df['RSI'] < rsi_melt_buy).rolling(window=confirm_w).sum() == confirm_w
        
        st.session_state['master'] = final_df[start_d:end_d]

# ==========================================
# 績效結果
# ==========================================
if 'master' in st.session_state:
    data = st.session_state['master']
    t1, t2 = st.tabs(["📊 監控", "⏳ 績效"])
    with t1:
        latest = data.iloc[-1]
        st.subheader(f"數據更新：{latest.name.strftime('%Y-%m-%d')}")
        c = st.columns(4); c[0].metric("價格", f"${latest['Close']:.2f}"); c[1].metric(f"RSI", f"{latest['RSI']:.1f}"); c[2].metric("VIX", f"{latest['Vix']:.1f}"); c[3].metric("回撤", f"{latest['Drawdown']:.1%}")

    with t2:
        total_init = init_core + init_rsv
        core, rsv = init_core, init_rsv
        shares, ac_bt, curr_m, hist = 0, 0, -1, []
        r15 = r25 = r35 = False
        bh_shrs = total_init / data['Close'].iloc[0]

        for date_idx, row in data.iterrows():
            p, r, v, sma, dd, s_sig, e_sig, m_sig = row['Close'], row['RSI'], row['Vix'], row['SMA'], row['Drawdown'], row['Speed_Sig'], row['Extra_Sig'], row['Melt_Sig']
            p_loss = (p - ac_bt) / ac_bt if ac_bt > 0 else 0
            
            # 預備金
            for d_trig, flag in [(-0.35, 'r35'), (-0.25, 'r25'), (-0.15, 'r15')]:
                if dd <= d_trig and not locals()[flag] and rsv >= init_rsv*0.3:
                    inv = init_rsv*0.3 if d_trig > -0.35 else rsv
                    shares += inv/p; rsv -= inv; exec(f"{flag}=True")
            if dd >= 0: r15 = r25 = r35 = False

            # DCA 規則
            if date_idx.month != curr_m:
                curr_m = date_idx.month
                is_melt = (p_loss < -0.15) or (p < sma) or (v > 40)
                amt = 0
                if is_melt:
                    if m_sig: amt = base_dca * 2
                else:
                    if e_sig: amt = base_dca * 4
                    elif s_sig: amt = base_dca * 2
                    else: amt = base_dca
                if amt > 0 and core >= amt: core -= amt; shares += amt/p
            
            ac_bt = (total_init - core - rsv) / shares if shares > 0 else 0
            hist.append({'Date': date_idx, 'S_Total': (shares*p)+core+rsv, 'B_Total': bh_shrs * p})
        
        res_df = pd.DataFrame(hist)
        st.table(pd.DataFrame([calculate_perf_metrics(res_df['S_Total'].values, total_init, res_df['Date']), 
                               calculate_perf_metrics(res_df['B_Total'].values, total_init, res_df['Date'])], 
                              index=["矛與盾", "B&H (大盤)"]).T)
        st.line_chart(res_df.set_index('Date')[['S_Total', 'B_Total']])
