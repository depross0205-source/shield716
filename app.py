import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, date

# ==========================================
# 系統初始化
# ==========================================
st.set_page_config(page_title="矛與盾 7.28 訊號確認版", page_icon="🛡️", layout="wide")
st.title("🛡️ 矛與盾 7.28 訊號確認量化系統 ⚔️")

# ==========================================
# 工具函數：技術指標與績效 (支援 LaTeX 運算)
# ==========================================
def calculate_perf_metrics(values, initial_capital, dates):
    returns = pd.Series(values).pct_change().dropna()
    total_return = (values[-1] - initial_capital) / initial_capital
    days = (dates.iloc[-1] - dates.iloc[0]).days
    years = days / 365.25 if days > 0 else 1
    # 年化報酬率公式: $CAGR = (\frac{Ending Value}{Beginning Value})^{1/years} - 1$
    cagr = (values[-1] / initial_capital) ** (1 / years) - 1
    std_dev = returns.std() * np.sqrt(52)
    sharpe = cagr / std_dev if std_dev != 0 else 0
    peak = pd.Series(values).cummax()
    mdd = ((pd.Series(values) - peak) / peak).min()
    return {"總報酬率": f"{total_return:.2%}", "年化報酬 (CAGR)": f"{cagr:.2%}", "最大回撤 (MDD)": f"{mdd:.2%}", "年化標準差": f"{std_dev:.2%}", "夏普指數": f"{sharpe:.2f}"}

def get_base_data(start, end):
    """抓取數據：2010前用 SPY 模擬 VOO"""
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
        return pd.DataFrame({'Close': full_voo['Close'], 'Vix': vix['Close']})

def calculate_rsi(data, periods=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).fillna(0); loss = (-delta.where(delta < 0, 0)).fillna(0)
    avg_gain = gain.ewm(com=periods - 1, min_periods=periods).mean(); avg_loss = loss.ewm(com=periods - 1, min_periods=periods).mean()
    return 100 - (100 / (1 + (avg_gain / avg_loss)))

# ==========================================
# 側邊欄：全參數調整
# ==========================================
st.sidebar.header("📅 1. 區間與資金")
start_d = st.sidebar.date_input("起始日", date(2003, 5, 1))
end_d = st.sidebar.date_input("結束日", date.today())
init_core = st.sidebar.number_input("核心資金 (NTD)", value=8000000)
init_rsv = st.sidebar.number_input("預備金 (NTD)", value=1000000)
base_dca = st.sidebar.number_input("基礎月扣額 (NTD)", value=200000)

st.sidebar.header("⚙️ 2. 訊號確認參數")
rsi_p = st.sidebar.number_input("RSI 週期", value=14)
# [span_2](start_span)重點：連續確認週數，預設 1，可調為 2-3[span_2](end_span)
confirm_w = st.sidebar.slider("訊號連續確認週數 (預設1)", 1, 5, 1)

with st.sidebar.expander("🔍 RSI 門檻詳細設定"):
    rsi_speed = st.slider("提速扣款 RSI 門檻", 30, 55, 45)
    rsi_extra = st.slider("超賣加碼 RSI 門檻", 20, 45, 35)
    rsi_melt_buy = st.slider("熔斷中加碼 RSI 門檻", 10, 40, 30)

up_file = st.sidebar.file_uploader("📥 3. 上傳 CSV (若有)", type=['csv'])

# ==========================================
# 數據整合引擎
# ==========================================
if st.sidebar.button("🔄 執行數據預整合", type="primary"):
    base_df = get_base_data(start_d, end_d)
    if up_file:
        df_csv = pd.read_csv(up_file, index_col=0, parse_dates=True)
        df_csv.index = df_csv.index.tz_localize(None)
        df_csv.columns = [c.capitalize() for c in df_csv.columns]
        base_df = pd.concat([df_csv, base_df])
        base_df = base_df[~base_df.index.duplicated(keep='last')]
    st.session_state['base_df'] = base_df.sort_index()

# ==========================================
# 手動修正與回測執行
# ==========================================
if 'base_df' in st.session_state:
    st.subheader("✍️ 數據補強：手動修正與補位")
    st.info("若聯網或 CSV 數據不齊 (NaN)，請在下方表格填入日期與數值進行修正。")
    correction_df = st.data_editor(pd.DataFrame(columns=["Date", "Close", "Vix"]), num_rows="dynamic", use_container_width=True)

    if st.button("🚀 確認數據並執行深度回測"):
        final_df = st.session_state['base_df'].copy()
        if not correction_df.empty:
            df_corr = correction_df.copy(); df_corr['Date'] = pd.to_datetime(df_corr['Date'])
            df_corr = df_corr.set_index('Date').tz_localize(None)
            final_df = pd.concat([final_df, df_corr])
            final_df = final_df[~final_df.index.duplicated(keep='last')].sort_index()
            
        final_df['RSI'] = calculate_rsi(final_df['Close'], periods=rsi_p)
        final_df['SMA'] = final_df['Close'].rolling(window=200, min_periods=1).mean()
        final_df['52W_High'] = final_df['Close'].rolling(window=52, min_periods=1).max()
        final_df['Drawdown'] = (final_df['Close'] - final_df['52W_High']) / final_df['52W_High']
        
        # [span_3](start_span)核心：連續訊號確認邏輯[span_3](end_span)
        final_df['Speed_Sig'] = (final_df['RSI'] < rsi_speed).rolling(window=confirm_w).sum() == confirm_w
        final_df['Extra_Sig'] = (final_df['RSI'] < rsi_extra).rolling(window=confirm_w).sum() == confirm_w
        final_df['Melt_Sig'] = (final_df['RSI'] < rsi_melt_buy).rolling(window=confirm_w).sum() == confirm_w
        
        st.session_state['master'] = final_df[start_d:end_d]

# ==========================================
# 顯示回測與績效結果
# ==========================================
if 'master' in st.session_state:
    data = st.session_state['master']
    t1, t2 = st.tabs(["📊 當前實時監控", "⏳ 2003年至今績效報告"])
    
    with t1:
        latest = data.iloc[-1]
        st.subheader(f"數據日期：{latest.name.strftime('%Y-%m-%d')}")
        if pd.isna(latest['Vix']): st.error("⚠️ VIX 資料缺失，請在上方修正表格補入數值。")
        c = st.columns(4); c[0].metric("價格", f"${latest['Close']:.2f}"); c[1].metric(f"週 RSI ({rsi_p})", f"{latest['RSI']:.1f}"); c[2].metric("VIX", f"{latest['Vix']:.1f}"); c[3].metric("距高回撤", f"{latest['Drawdown']:.1%}")

    with t2:
        total_init = init_core + init_rsv
        core, rsv = init_core, init_rsv
        shares, ac_bt, curr_m, hist = 0, 0, -1, []
        r15 = r25 = r35 = False
        bh_shrs = total_init / data['Close'].iloc[0]

        for date_idx, row in data.iterrows():
            p, r, v, sma, dd, s_sig, e_sig, m_sig = row['Close'], row['RSI'], row['Vix'], row['SMA'], row['Drawdown'], row['Speed_Sig'], row['Extra_Sig'], row['Melt_Sig']
            p_loss = (p - ac_bt) / ac_bt if ac_bt > 0 else 0
            
            for d_trig, flag in [(-0.35, 'r35'), (-0.25, 'r25'), (-0.15, 'r15')]:
                if dd <= d_trig and not locals()[flag] and rsv >= init_rsv*0.3:
                    inv = init_rsv*0.3 if d_trig > -0.35 else rsv
                    shares += inv/p; rsv -= inv; exec(f"{flag}=True")
            if dd >= 0: r15 = r25 = r35 = False

            if date_idx.month != curr_m:
                curr_m = date_idx.month
                is_melt = (p_loss < -0.15) or (p < sma) or (v > 40)
                amt = 0
                if is_melt:
                    [span_4](start_span)if m_sig: amt = base_dca * 2 # 熔斷連續達標加碼[span_4](end_span)
                else:
                    [span_5](start_span)if e_sig: amt = base_dca * 4 # 超賣連續達標[span_5](end_span)
                    [span_6](start_span)elif s_sig: amt = base_dca * 2 # 提速連續達標[span_6](end_span)
                    else: amt = base_dca
                if amt > 0 and core >= amt: core -= amt; shares += amt/p
            
            ac_bt = (total_init - core - rsv) / shares if shares > 0 else 0
            hist.append({'Date': date_idx, 'S_Total': (shares*p)+core+rsv, 'B_Total': bh_shrs * p})
        
        res_df = pd.DataFrame(hist)
        st.markdown("#### 🏆 矛與盾策略 v.s. Buy & Hold 指標對比")
        st.table(pd.DataFrame([calculate_perf_metrics(res_df['S_Total'].values, total_init, res_df['Date']), 
                               calculate_perf_metrics(res_df['BH_Total'].values, total_init, res_df['Date'])], 
                              index=["矛與盾策略", "Buy & Hold (大盤)"]).T)
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=res_df['Date'], y=res_df['S_Total'], name='矛與盾淨值', line=dict(color='#00FFCC', width=3)))
        fig.add_trace(go.Scatter(x=res_df['Date'], y=res_df['BH_Total'], name='大盤 B&H', line=dict(color='#888888', dash='dot')))
        fig.update_layout(template="plotly_dark", height=500, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)
