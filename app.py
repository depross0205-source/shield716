import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, date

# ==========================================
# 1. 系統配置 (相容 Streamlit Cloud 1.55.0+)
# ==========================================
st.set_page_config(page_title="矛與盾 9.00", page_icon="🛡️", layout="wide")
st.title("🛡️ 矛與盾 v9.00 量化回測系統 ⚔️")

# ==========================================
# 2. 核心計算工具
# ==========================================
def get_rsi(s, period=14):
    """計算 RSI 指標"""
    delta = s.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(com=period-1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period-1, min_periods=period).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    return 100 - (100 / (1 + rs))

def normalize_factors(df):
    """識別並對齊因子，Close 強制同步 SP500"""
    if df.empty: return df
    df = df.reset_index()
    df.columns = [str(c).strip().upper() for c in df.columns]
    res = pd.DataFrame()

    # 識別日期
    date_col = next((c for c in df.columns if any(k in c for k in ['DATE', 'TIME', '日期'])), None)
    if date_col:
        res['Date_Final'] = pd.to_datetime(df[date_col], errors='coerce')

    # 因子映射
    mapping = {
        'SP500': ['SP500', 'VOO', 'PRICE', '收盤', 'CLOSE'],
        'SP500EW': ['RSP', 'EW', '等權重'],
        'HY_SPREAD': ['SPREAD', 'HY_SPREAD', '利差'],
        'TIPS_10Y': ['TIPS', 'TIPS_10Y', '實質利率'],
        'VIX': ['VIX', '恐慌', '^VIX'],
        'CAPE': ['CAPE', '席勒', '本益比']
    }

    for target_key, kws in mapping.items():
        for col in df.columns:
            if any(kw in col for kw in kws) and target_key not in res.columns:
                res[target_key] = pd.to_numeric(
                    df[col].astype(str).str.replace(',', '').str.replace('$', ''), 
                    errors='coerce'
                )
                break

    if 'SP500' in res.columns:
        res['Close'] = res['SP500']

    for col in df.columns:
        if col not in list(res.columns) + [date_col]:
            res[col] = df[col]

    return res.dropna(subset=['Date_Final'])

def get_web_data(start_date, end_date):
    """聯網補強數據"""
    try:
        spy = yf.Ticker("SPY").history(start=start_date, end=end_date, interval="1wk")
        vix = yf.Ticker("^VIX").history(start=start_date, end=end_date, interval="1wk")
        for d in [spy, vix]:
            if not d.empty: d.index = d.index.tz_localize(None)
        web_df = pd.DataFrame(index=spy.index)
        web_df['SP500_Web'] = spy['Close']
        web_df['VIX_Web'] = vix['Close']
        web_df.index.name = 'Date_Final'
        return web_df.reset_index()
    except Exception as e:
        st.warning(f"⚠️ 聯網失敗: {str(e)}")
        return pd.DataFrame()

# ==========================================
# 3. 側邊欄設定 (1000 萬資產配置)
# ==========================================
st.sidebar.header("💰 1. 資產配置")
TOTAL_W = st.sidebar.number_input("總資產 (萬 NTD)", value=1000)
TOTAL_CAP = TOTAL_W * 10000

CASH_W = st.sidebar.number_input("預備金 (萬 NTD)", value=200)
CASH_RSV = CASH_W * 10000

DCA_POOL = TOTAL_CAP - CASH_RSV
base_dca_w = st.sidebar.number_input("每月 DCA (萬 NTD)", value=20)
base_dca = base_dca_w * 10000

st.sidebar.header("🛡️ 2. 熔斷參數")
M_LOSS = st.sidebar.slider("虧損熔斷 (%)", -30, -5, -15) / 100
M_SMA = st.sidebar.number_input("均線週數", value=200)
M_VIX = st.sidebar.slider("VIX 門檻", 20, 60, 40)

st.sidebar.header("⚙️ 3. 買進設定")
RSI_PERIOD = st.sidebar.number_input("RSI 週期", value=14)
RSI_LV1 = st.sidebar.slider("超賣爆買 RSI (4x)", 20, 45, 35)
RSI_LV2 = st.sidebar.slider("提速加碼 RSI (2x)", 30, 55, 45)

up_file = st.sidebar.file_uploader("📥 4. 上傳 CSV 資料庫", type=['csv'])

# ==========================================
# 4. 數據載入 (徹底修復 SyntaxError)
# ==========================================
if st.sidebar.button("🚀 執行數據整合", type="primary"):
    web_df = get_web_data(date(2005, 1, 1), date.today())
    if up_file:
        df_csv = normalize_factors(pd.read_csv(up_file))
        df_csv = df_csv.loc[:, ~df_csv.columns.duplicated()].copy()
        df_csv = df_csv.drop_duplicates(subset=['Date_Final'])
        
        if not web_df.empty:
            web_df = web_df.drop_duplicates(subset=['Date_Final'])
            final = pd.merge(web_df, df_csv, on='Date_Final', how='outer')
        else:
            final = df_csv
            
        for f in ['SP500', 'VIX']:
            web_c = f"{f}_Web"
            if web_c in final.columns:
                if f not in final.columns: final[f] = final[web_c]
                else: final[f] = final[f].combine_first(final[web_c])
        
        final['Close'] = final['SP500']
        final = final.drop(columns=[c for c in final.columns if '_Web' in c])
        # 拆解成多行，防止 SyntaxError
        name_map = {'Date_Final': 'Date'}
        final = final.rename(columns=name_map)
    else:
        if web_df.empty: st.stop()
        final = web_df.rename(columns={'Date_Final': 'Date', 'SP500_Web': 'SP500', 'VIX_Web': 'VIX'})
        final['Close'] = final['SP500']
    
    final = final.copy().sort_values('Date').ffill()
    st.session_state['master_df'] = final.dropna(subset=['Date', 'Close'])
    st.success(f"✅ 已加載 {len(st.session_state['master_df'])} 筆數據")

# ==========================================
# 5. 面板與回測
# ==========================================
if 'master_df' not in st.session_state:
    st.info("💡 請上傳 CSV 或執行數據整合")
    st.stop()

df = st.session_state['master_df'].copy()
df['RSI'] = get_rsi(df['Close'], RSI_PERIOD)
df['SMA'] = df['Close'].rolling(window=M_SMA, min_periods=1).mean()
df['DD'] = (df['Close'] - df['Close'].rolling(window=52, min_periods=1).max()) / df['Close'].rolling(window=52, min_periods=1).max()

tab1, tab2 = st.tabs(["📊 即時監控", "⏳ 歷史回測"])

with tab1:
    latest = df.iloc[-1]
    st.subheader(f"基準日: {latest['Date'].strftime('%Y-%m-%d')}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("價格", f"${latest['Close']:.2f}")
    c2.metric("RSI", f"{latest['RSI']:.1f}")
    c3.metric("VIX", f"{latest.get('VIX', 0):.1f}")
    c4.metric("回撤", f"{latest['DD']:.1%}")

    st.markdown("---")
    cost = st.number_input("成本", value=450.0)
    loss = (latest['Close'] - cost) / cost if cost > 0 else 0
    is_melt = loss < M_LOSS or latest['Close'] < latest['SMA'] or latest.get('VIX', 0) > M_VIX

    if is_melt: st.error("🔴 目前狀態：熔斷模式啟動")
    else:
        if latest['RSI'] < RSI_LV1: st.warning(f"🔥 超賣爆買 ({base_dca*4/10000:.0f}萬)")
        elif latest['RSI'] < RSI_LV2: st.warning(f"🟡 提速加碼 ({base_dca*2/10000:.0f}萬)")
        else: st.success(f"🔵 基礎 DCA ({base_dca/10000:.0f}萬)")
    st.dataframe(df.tail(10), width=1200)

with tab2:
    st.subheader("1000 萬資產回測報告")
    shares, dca_p, rsv_p, curr_m, hist = 0, DCA_POOL, CASH_RSV, -1, []
    bh_sh = TOTAL_CAP / df['Close'].iloc[0]
    r_flags = {'r15': False, 'r25': False, 'r35': False}
    
    for idx, row in df.iterrows():
        p, dd = row['Close'], row['DD']
        ac_bt = (TOTAL_CAP - dca_p - rsv_p) / shares if shares > 0 else 0
        loss_bt = (p - ac_bt) / ac_bt if ac_bt > 0 else 0
        
        for trg, k in [(-0.15, 'r15'), (-0.25, 'r25'), (-0.35, 'r35')]:
            if dd <= trg and not r_flags[k] and rsv_p >= CASH_RSV * 0.3:
                inv = CASH_RSV * 0.3 if trg > -0.35 else rsv_p
                shares += inv / p; rsv_p -= inv; r_flags[k] = True
        if dd >= 0: r_flags = {k: False for k in r_flags}
        
        if row['Date'].month != curr_m:
            curr_m = row['Date'].month
            melt_bt = loss_bt < M_LOSS or p < row['SMA'] or row.get('VIX', 0) > M_VIX
            amt = 0
            if not melt_bt:
                if row['RSI'] < RSI_LV1: amt = base_dca * 4
                elif row['RSI'] < RSI_LV2: amt = base_dca * 2
                else: amt = base_dca
            if amt > 0 and dca_p >= amt: dca_p -= amt; shares += amt / p
        hist.append({'Date': row['Date'], 'Strategy': shares * p + dca_p + rsv_p, 'BH': bh_sh * p})
    
    res = pd.DataFrame(hist).set_index('Date')
    st.line_chart(res)
    
    def calc_perf(v_ser):
        tr = (v_ser.iloc[-1] - TOTAL_CAP) / TOTAL_CAP
        years = len(v_ser) / 52
        cagr = (v_ser.iloc[-1] / TOTAL_CAP) ** (1 / years) - 1 if years > 0 else 0
        mdd = ((v_ser - v_ser.cummax()) / v_ser.cummax()).min()
        rets = v_ser.pct_change(fill_method=None).dropna()
        sharpe = (cagr - 0.02) / (rets.std() * np.sqrt(52)) if rets.std() > 0 else 0
        return [f"{tr:.2%}", f"{cagr:.2%}", f"{mdd:.2%}", f"{sharpe:.2f}"]
    
    st.table(pd.DataFrame({"指標": ["總報酬", "年化報酬", "最大回撤", "夏普值"],
                           "矛與盾策略": calc_perf(res['Strategy']),
                           "Buy & Hold": calc_perf(res['BH'])}))

st.markdown("---")
st.caption("v9.00 Ultimate Cloud Edition | 完美修復 SyntaxError 與 10M 資金邏輯")
