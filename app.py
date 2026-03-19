import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, date

# ==========================================
# 系統設定
# ==========================================
st.set_page_config(page_title="矛與盾 7.22 終極整合版", page_icon="🛡️", layout="wide")
st.title("🛡️ 矛與盾 7.22 全功能量化系統 ⚔️")

# ==========================================
# 核心計算與數據處理
# ==========================================
def calculate_metrics(values, initial_capital, dates):
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

def get_web_data(start, end):
    """抓取數據：2010前用 SPY 模擬 VOO"""
    with st.spinner("正在聯網校準 VOO/SPY/VIX 數據..."):
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
        
        df = pd.DataFrame({'Close': full_voo['Close'], 'Vix': vix['Close']}).ffill()
        return df

def calculate_rsi(data, periods=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)
    avg_gain = gain.ewm(com=periods - 1, min_periods=periods).mean()
    avg_loss = loss.ewm(com=periods - 1, min_periods=periods).mean()
    return 100 - (100 / (1 + (avg_gain / avg_loss)))

# ==========================================
# 側邊欄：超詳盡參數與手動輸入
# ==========================================
st.sidebar.header("📅 1. 時間與資金")
start_d = st.sidebar.date_input("回測起始日", date(2003, 5, 1))
end_d = st.sidebar.date_input("回測結束日", date.today())
init_core = st.sidebar.number_input("核心資金 (NTD)", value=8000000)
init_rsv = st.sidebar.number_input("預備金總額 (NTD)", value=1000000)
base_dca = st.sidebar.number_input("基礎月扣額 (NTD)", value=200000)

st.sidebar.header("⚙️ 2. 策略規則參數")
with st.sidebar.expander("買進/加碼/熔斷 RSI 設定"):
    rsi_p = st.number_input("RSI 週期 (週)", value=14)
    consecutive_w = st.number_input("訊號需連續維持週數", value=1, min_value=1)
    rsi_speed_up = st.slider("提速加碼 RSI (40萬)", 30, 55, 45)
    rsi_extra_add = st.slider("超賣爆買 RSI (80萬)", 20, 45, 35)
    rsi_meltdown_buy = st.slider("熔斷中允許買入 RSI", 10, 40, 30)
    rsi_sell = st.slider("高檔獲利減碼 RSI", 60, 95, 80)

st.sidebar.header("💾 3. 數據補強中心")
with st.sidebar.expander("✍️ 手動輸入/補齊數據"):
    st.write("若聯網數據不準，可在下方直接修正 (Date, Close, Vix)")
    manual_data = st.data_editor(
        pd.DataFrame(columns=["Date", "Close", "Vix"]),
        num_rows="dynamic",
        use_container_width=True
    )

up_file = st.sidebar.file_uploader("📥 上傳歷史 CSV", type=['csv'])

# ==========================================
# 數據整合與執行
# ==========================================
if st.sidebar.button("🚀 執行全自動數據整合與回測", type="primary"):
    # A. 聯網抓取基礎
    df_main = get_web_data(start_d, end_d)
    
    # B. 拼接 CSV
    if up_file:
        df_csv = pd.read_csv(up_file, index_col=0, parse_dates=True)
        df_csv.index = df_csv.index.tz_localize(None)
        df_csv.columns = [c.capitalize() for c in df_csv.columns]
        df_main = pd.concat([df_csv, df_main])
        df_main = df_main[~df_main.index.duplicated(keep='last')]

    # C. 拼接手動輸入 (優先級最高)
    if not manual_data.empty:
        df_manual = manual_data.copy()
        df_manual['Date'] = pd.to_datetime(df_manual['Date'])
        df_manual = df_manual.set_index('Date').tz_localize(None)
        df_main = pd.concat([df_main, df_manual])
        df_main = df_main[~df_main.index.duplicated(keep='last')]

    # D. 計算指標
    df_main = df_main.sort_index()
    df_main['RSI'] = calculate_rsi(df_main['Close'], periods=rsi_p)
    df_main['SMA'] = df_main['Close'].rolling(window=200, min_periods=1).mean()
    df_main['52W_High'] = df_main['Close'].rolling(window=52, min_periods=1).max()
    df_main['Drawdown'] = (df_main['Close'] - df_main['52W_High']) / df_main['52W_High']
    st.session_state['master'] = df_main[start_d:end_d]
    st.sidebar.success("✅ 數據拼接完成")

# ==========================================
# 主介面：監控與報告
# ==========================================
if 'master' in st.session_state:
    data = st.session_state['master']
    t1, t2 = st.tabs(["📊 實時狀態監控", "⏳ 深度績效報告"])
    
    with t1:
        latest = data.iloc[-1]
        st.subheader(f"數據基準日：{latest.name.strftime('%Y-%m-%d')}")
        if pd.isna(latest['Vix']): st.warning("⚠️ 警告：目前聯網 VIX 數據缺失，請至左側手動補齊。")
        
        col = st.columns(4)
        col[0].metric("最新價格", f"${latest['Close']:.2f}")
        col[1].metric(f"週 RSI ({rsi_p})", f"{latest['RSI']:.1f}")
        col[2].metric("VIX 恐慌指數", f"{latest['Vix']:.1f}")
        col[3].metric("距高點回撤", f"{latest['Drawdown']:.1%}")
        
    with t2:
        total_init = init_core + init_rsv
        core, rsv = init_core, init_rsv
        shares, ac_bt, curr_m, hist = 0, 0, -1, []
        r15 = r25 = r35 = False
        bh_shares = total_init / data['Close'].iloc[0]

        # 連續週數判定
        data['Sig'] = (data['RSI'] < rsi_speed_up).rolling(window=consecutive_w).sum() >= consecutive_w

        for date_idx, row in data.iterrows():
            p, r, v, sma, dd, sig = row['Close'], row['RSI'], row['Vix'], row['SMA'], row['Drawdown'], row['Sig']
            p_loss = (p - ac_bt) / ac_bt if ac_bt > 0 else 0
            
            # 預備金 (MDD 觸發)
            for d_trig, flag in [(-0.35, 'r35'), (-0.25, 'r25'), (-0.15, 'r15')]:
                if dd <= d_trig and not locals()[flag] and rsv >= init_rsv*0.3:
                    inv = init_rsv*0.3 if d_trig > -0.35 else rsv
                    shares += inv/p; rsv -= inv; exec(f"{flag}=True")
            if dd >= 0: r15 = r25 = r35 = False

            # 每月 DCA
            if date_idx.month != curr_m:
                curr_m = date_idx.month
                is_melt = (p_loss < -0.15) or (p < sma) or (v > 40)
                amt = 0
                if is_melt:
                    if r < rsi_meltdown_buy: amt = base_dca * 2
                else:
                    if r < rsi_extra_add and sig: amt = base_dca * 4
                    elif r < rsi_speed_up and sig: amt = base_dca * 2
                    elif r > rsi_sell: amt = 0 
                    else: amt = base_dca
                if amt > 0 and core >= amt: core -= amt; shares += amt/p
            
            ac_bt = (total_init - core - rsv) / shares if shares > 0 else 0
            hist.append({'Date': date_idx, 'S_Total': (shares*p)+core+rsv, 'B_Total': bh_shares * p})
        
        res_df = pd.DataFrame(hist)
        st.markdown("#### 🏆 策略績效與 B&H 對比表")
        s_m = calculate_metrics(res_df['S_Total'].values, total_init, res_df['Date'])
        b_m = calculate_metrics(res_df['B_Total'].values, total_init, res_df['Date'])
        st.table(pd.DataFrame([s_m, b_m], index=["矛與盾策略", "Buy & Hold (大盤)"]).T)
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=res_df['Date'], y=res_df['S_Total'], name='策略淨值', line=dict(color='#00FFCC', width=3)))
        fig.add_trace(go.Scatter(x=res_df['Date'], y=res_df['B_Total'], name='大盤 B&H', line=dict(color='#888888', dash='dot')))
        fig.update_layout(template="plotly_dark", height=500, margin=dict(l=20, r=20, t=50, b=20), hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("💡 操作提示：1. 設定回測期間 (2003 起) 2. 必要時手動補足 VIX 3. 點擊執行按鈕。")
