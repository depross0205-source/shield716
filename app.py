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
st.set_page_config(page_title="矛與盾 7.18 專業績效版", page_icon="🛡️", layout="wide")
st.title("🛡️ 矛與盾 7.18 專業量化系統 ⚔️")

def safe_divider():
    try: st.divider()
    except AttributeError: st.markdown("---")

# ==========================================
# 工具函數：技術指標與績效計算
# ==========================================
def calculate_metrics(values, initial_capital):
    """計算量化指標：總報酬、年化、MDD、標準差、夏普"""
    returns = pd.Series(values).pct_change().dropna()
    total_return = (values[-1] - initial_capital) / initial_capital
    
    # 計算年資
    days = (res_df['Date'].iloc[-1] - res_df['Date'].iloc[0]).days
    years = days / 365.25 if days > 0 else 1
    cagr = (values[-1] / initial_capital) ** (1 / years) - 1
    
    # 風險指標 (以週線資料進行年化處理)
    std_dev = returns.std() * np.sqrt(52)
    sharpe = cagr / std_dev if std_dev != 0 else 0
    
    # 最大回撤
    peak = pd.Series(values).cummax()
    drawdown = (pd.Series(values) - peak) / peak
    mdd = drawdown.min()
    
    return {
        "總報酬率": f"{total_return:.2%}",
        "年化報酬 (CAGR)": f"{cagr:.2%}",
        "最大回撤 (MDD)": f"{mdd:.2%}",
        "年化標準差": f"{std_dev:.2%}",
        "夏普指數": f"{sharpe:.2f}"
    }

def normalize_data(df):
    if df.empty: return df
    df.index = pd.to_datetime(df.index).tz_localize(None)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).capitalize() for c in df.columns]
    if 'Price' in df.columns and 'Close' not in df.columns:
        df = df.rename(columns={'Price': 'Close'})
    if 'Close' not in df.columns: return pd.DataFrame()
    
    clean_df = pd.DataFrame()
    clean_df['Close'] = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
    clean_df['Vix'] = df['Vix'].iloc[:, 0] if ('Vix' in df.columns and isinstance(df['Vix'], pd.DataFrame)) else df.get('Vix', 20.0)
    return clean_df

def process_metrics(df):
    df = df.copy().sort_index()
    df['RSI_14'] = calculate_rsi(df['Close'], periods=14)
    df['200_SMA'] = df['Close'].rolling(window=200, min_periods=1).mean()
    df['52W_High'] = df['Close'].rolling(window=52, min_periods=1).max()
    df['Drawdown'] = (df['Close'] - df['52W_High']) / df['52W_High']
    return df.dropna(subset=['Close', 'RSI_14'])

def calculate_rsi(data, periods=14):
    delta = data.diff(); gain = (delta.where(delta > 0, 0)).fillna(0); loss = (-delta.where(delta < 0, 0)).fillna(0)
    avg_gain = gain.ewm(com=periods - 1, min_periods=periods).mean(); avg_loss = loss.ewm(com=periods - 1, min_periods=periods).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# ==========================================
# 側邊欄設定
# ==========================================
st.sidebar.header("📅 回測期間設定")
start_date_input = st.sidebar.date_input("起始日期", date(2003, 1, 1))
end_date_input = st.sidebar.date_input("結束日期", date.today())

st.sidebar.header("⚙️ 策略參數")
init_core = st.sidebar.number_input("核心初始資金 (NTD)", value=8000000)
init_rsv = st.sidebar.number_input("預備金總額 (NTD)", value=1000000)
base_dca = st.sidebar.number_input("基礎每月 DCA (NTD)", value=200000)

up_file = st.sidebar.file_uploader("📥 上傳歷史 CSV (選填)", type=['csv'])

# ==========================================
# 核心數據處理
# ==========================================
if st.sidebar.button("🚀 執行數據整合與回測", type="primary"):
    with st.spinner("正在拼接數據與運算..."):
        # A. 處理 CSV
        df_csv = normalize_data(pd.read_csv(up_file, index_col=0, parse_dates=True)) if up_file else pd.DataFrame()
        
        # B. 抓取聯網數據 (根據設定期間)
        df_yf = pd.DataFrame()
        try:
            # 由於 VOO 2010 才上市，若早於 2010 建議用 SPY 模擬，此處維持 VOO 並給予提示
            v_raw = yf.Ticker("VOO").history(start=start_date_input, end=end_date_input, interval="1wk")
            x_raw = yf.Ticker("^VIX").history(start=start_date_input, end=end_date_input, interval="1wk")
            df_yf = pd.DataFrame({'Close': normalize_data(v_raw)['Close'], 'Vix': normalize_data(x_raw).get('Vix', 20.0)}).dropna()
        except: pass

        combined = pd.concat([df_csv, df_yf]) if not df_csv.empty and not df_yf.empty else (df_csv if not df_csv.empty else df_yf)
        
        if not combined.empty:
            combined = combined[~combined.index.duplicated(keep='last')].sort_index()
            # 過濾日期區間
            combined = combined[start_date_input:end_date_input]
            st.session_state['master'] = process_metrics(combined)
            st.sidebar.success(f"✅ 數據載入成功 ({len(combined)} 筆)")
        else:
            st.sidebar.error("❌ 找不到該期間資料")

# ==========================================
# 主介面
# ==========================================
if 'master' in st.session_state:
    data = st.session_state['master']
    t1, t2 = st.tabs(["📊 當前監控", "⏳ 績效分析報告"])
    
    with t1:
        latest = data.iloc[-1]
        st.subheader(f"基準日：{latest.name.strftime('%Y-%m-%d')}")
        cost = st.number_input("您的 VOO 平均成本", value=450.0)
        c = st.columns(4); c[0].metric("最新價格", f"${latest['Close']:.2f}"); c[1].metric("週 RSI", f"{latest['RSI_14']:.1f}"); c[2].metric("VIX", f"{latest['Vix']:.1f}"); c[3].metric("回撤", f"{latest['Drawdown']:.1%}")
        safe_divider()
        # 買賣規則邏輯 (略，與前版相同)

    with t2:
        st.subheader("⚔️ 策略 v.s. 大盤 (B&H)")
        
        # 回測邏輯運算
        total_init = init_core + init_rsv
        core, rsv = init_core, init_rsv
        shares, ac_bt, curr_m, hist = 0, 0, -1, []
        r15 = r25 = r35 = False

        # B&H 計算 (第一天全入)
        bh_shares = total_init / data['Close'].iloc[0]

        for date_idx, row in data.iterrows():
            p, r, v, sma, dd = row['Close'], row['RSI_14'], row['Vix'], row['200_SMA'], row['Drawdown']
            p_loss_bt = (p - ac_bt) / ac_bt if ac_bt > 0 else 0
            
            # 策略預備金與 DCA 邏輯
            for d_trig, flag in [(-0.35, 'r35'), (-0.25, 'r25'), (-0.15, 'r15')]:
                if dd <= d_trig and not locals()[flag] and rsv >= init_rsv*0.3:
                    inv = init_rsv*0.3 if d_trig > -0.35 else rsv
                    shares += inv/p; rsv -= inv; exec(f"{flag}=True")
            if dd >= 0: r15 = r25 = r35 = False
            if date_idx.month != curr_m:
                curr_m = date_idx.month
                is_m_bt = (p_loss_bt < -0.15) or (p < sma) or (v > 40)
                amt = (base_dca*2 if r < 30 else 0) if is_m_bt else (base_dca*4 if r < 35 else (base_dca*2 if r < 45 else base_dca))
                if amt > 0 and core >= amt: core -= amt; shares += amt/p
            
            ac_bt = (total_init - core - rsv) / shares if shares > 0 else 0
            # 紀錄兩組價值
            hist.append({
                'Date': date_idx, 
                'Strategy_Total': (shares*p)+core+rsv, 
                'BH_Total': bh_shares * p
            })
        
        res_df = pd.DataFrame(hist)
        
        # 績效表呈現
        st.markdown("#### 📈 績效指標對比")
        s_metrics = calculate_metrics(res_df['Strategy_Total'].values, total_init)
        b_metrics = calculate_metrics(res_df['BH_Total'].values, total_init)
        
        metrics_comp = pd.DataFrame([s_metrics, b_metrics], index=["矛與盾策略", "Buy & Hold (大盤)"]).T
        st.table(metrics_comp)
        
        # 曲線圖
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=res_df['Date'], y=res_df['Strategy_Total'], name='矛與盾策略', line=dict(color='#00FFCC', width=3)))
        fig.add_trace(go.Scatter(x=res_df['Date'], y=res_df['BH_Total'], name='大盤持有 (B&H)', line=dict(color='#888888', dash='dot')))
        fig.update_layout(title="資產成長曲線對比", template="plotly_dark", height=500)
        st.plotly_chart(fig, use_container_width=True)

else:
    st.info("請於左側設定回測日期區間（2003至今）並點擊執行按鈕。")
