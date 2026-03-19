import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ==========================================
# 系統初始化與版本防護
# ==========================================
st.set_page_config(page_title="矛與盾 7.16 專業回測版", page_icon="🛡️", layout="wide")
st.title("🛡️ 矛與盾 7.16 專業數據系統 ⚔️")

def safe_divider():
    try:
        st.divider()
    except AttributeError:
        st.markdown("---")

# ==========================================
# 工具函數：技術指標與數據標準化
# ==========================================
def calculate_rsi(data, periods=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)
    avg_gain = gain.ewm(com=periods - 1, min_periods=periods).mean()
    avg_loss = loss.ewm(com=periods - 1, min_periods=periods).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def normalize_data(df):
    if df.empty: return df
    df.index = pd.to_datetime(df.index).tz_localize(None)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    # 支援不分大小寫的 Close 或 Price 欄位
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

# ==========================================
# 側邊欄：回測參數設定 (全參數開放)
# ==========================================
st.sidebar.header("⚙️ 策略參數設定")
with st.sidebar.expander("💰 資金配置", expanded=True):
    init_core = st.number_input("核心初始資金 (NTD)", value=8000000, step=100000)
    init_rsv = st.number_input("預備金總額 (NTD)", value=1000000, step=100000)
    base_dca = st.number_input("基礎每月 DCA (NTD)", value=200000, step=10000)

with st.sidebar.expander("📉 RSI 觸發閾值", expanded=True):
    rsi_melt = st.slider("熔斷加碼區 (RSI < X)", 20, 35, 30)
    rsi_os = st.slider("超賣加碼區 (RSI < X)", 30, 45, 35)
    rsi_weak = st.slider("提速扣款區 (RSI < X)", 40, 55, 45)

st.sidebar.markdown("---")
up_file = st.sidebar.file_uploader("📥 上傳歷史 CSV (選填)", type=['csv'])

# ==========================================
# 數據整合引擎
# ==========================================
if st.sidebar.button("🚀 執行數據整合與回測", type="primary"):
    with st.spinner("數據處理中..."):
        df_csv = normalize_data(pd.read_csv(up_file, index_col=0, parse_dates=True)) if up_file else pd.DataFrame()
        df_yf = pd.DataFrame()
        try:
            v_raw = yf.Ticker("VOO").history(period="10y", interval="1wk")
            x_raw = yf.Ticker("^VIX").history(period="10y", interval="1wk")
            df_yf = pd.DataFrame({'Close': normalize_data(v_raw)['Close'], 'Vix': normalize_data(x_raw).get('Vix', 20.0)}).dropna()
        except: pass

        if not df_csv.empty and not df_yf.empty:
            combined = pd.concat([df_csv, df_yf])
            combined = combined[~combined.index.duplicated(keep='last')].sort_index()
        else:
            combined = df_csv if not df_csv.empty else df_yf
            
        if not combined.empty:
            st.session_state['master'] = process_metrics(combined)
            st.sidebar.success("✅ 數據載入成功")
        else:
            st.sidebar.error("❌ 找不到有效數據")

# ==========================================
# 顯示介面
# ==========================================
if 'master' in st.session_state:
    data = st.session_state['master']
    t1, t2 = st.tabs(["📊 當前監控", "⏳ 完整回測報告"])
    
    with t1:
        latest = data.iloc[-1]
        st.subheader(f"數據基準日：{latest.name.strftime('%Y-%m-%d')}")
        cost = st.number_input("您的平均成本", value=450.0)
        c = st.columns(4)
        c[0].metric("最新價格", f"${latest['Close']:.2f}")
        c[1].metric("週 RSI", f"{latest['RSI_14']:.1f}")
        c[2].metric("VIX", f"{latest['Vix']:.1f}")
        c[3].metric("回撤", f"{latest['Drawdown']:.1%}")
        
        loss = (latest['Close'] - cost) / cost
        is_melt = loss < -0.15 or latest['Close'] < latest['200_SMA'] or latest['Vix'] > 40
        safe_divider()
        if is_melt:
            st.error("🔴 模式：熔斷啟動中")
            st.write("執行建議：" + ("允許單次加碼" if latest['RSI_14'] < rsi_melt else "暫停 DCA"))
        else:
            st.success("🟢 模式：運行正常")
            if latest['RSI_14'] < rsi_os: st.warning(f"加碼扣款 ({base_dca*4/10000:.0f}萬)")
            elif latest['RSI_14'] < rsi_weak: st.warning(f"提速扣款 ({base_dca*2/10000:.0f}萬)")
            else: st.info(f"基礎扣款 ({base_dca/10000:.0f}萬)")

    with t2:
        st.subheader("策略回測結果")
        core, rsv = init_core, init_rsv
        shares, ac_bt, curr_m, hist = 0, 0, -1, []
        r15 = r25 = r35 = False

        for date, row in data.iterrows():
            p, r, v, sma, dd = row['Close'], row['RSI_14'], row['Vix'], row['200_SMA'], row['Drawdown']
            p_loss_bt = (p - ac_bt) / ac_bt if ac_bt > 0 else 0
            
            # 預備金邏輯 (15%/25%/35% 分段投入)
            for d_trig, flag in [(-0.35, 'r35'), (-0.25, 'r25'), (-0.15, 'r15')]:
                if dd <= d_trig and not locals()[flag] and rsv >= init_rsv*0.3:
                    inv = init_rsv*0.3 if d_trig > -0.35 else rsv
                    shares += inv/p; rsv -= inv; exec(f"{flag}=True")
            if dd >= 0: r15 = r25 = r35 = False

            # 每月定額邏輯
            if date.month != curr_m:
                curr_m = date.month
                is_m_bt = (p_loss_bt < -0.15) or (p < sma) or (v > 40)
                amt = (base_dca*2 if r < rsi_melt else 0) if is_m_bt else (base_dca*4 if r < rsi_os else (base_dca*2 if r < rsi_weak else base_dca))
                if amt > 0 and core >= amt: core -= amt; shares += amt/p
                
            ac_bt = (init_core - core + init_rsv - rsv) / shares if shares > 0 else 0
            hist.append({'Date': date, 'Total': (shares*p)+core+rsv, 'Price': p, 'Cost': ac_bt})
        
        res_df = pd.DataFrame(hist)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
        fig.add_trace(go.Scatter(x=res_df['Date'], y=res_df['Total'], name='資產淨值'), row=1, col=1)
        fig.add_trace(go.Scatter(x=res_df['Date'], y=res_df['Price'], name='VOO 股價'), row=2, col=1)
        fig.add_trace(go.Scatter(x=res_df['Date'], y=res_df['Cost'], name='持有均價'), row=2, col=1)
        fig.update_layout(height=600, template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)
        st.success(f"回測結束！區間報酬率：{(res_df.iloc[-1]['Total']-(init_core+init_rsv))/(init_core+init_rsv):.2%}")
else:
    st.info("請於左側選單設定參數，並點擊執行。")
