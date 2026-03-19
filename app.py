import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, date

# ==========================================
# 1. 系統基礎配置 (相容所有環境)
# ==========================================
st.set_page_config(page_title="矛與盾 9.10", page_icon="🛡️", layout="wide")
st.title("🛡️ 矛與盾 v9.10 模組化穩定系統 ⚔️")

# ==========================================
# 2. 核心運算模組
# ==========================================
def get_rsi(s, period=14):
    """計算 RSI 數值"""
    delta = s.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(com=period-1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period-1, min_periods=period).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    return 100 - (100 / (1 + rs))

def normalize_factors(df):
    """因子標準化模組：保留所有原始數據"""
    if df.empty: return df
    df = df.reset_index()
    # 統一轉大寫並清理
    df.columns = [str(c).strip().upper() for c in df.columns]
    res = pd.DataFrame()

    # 識別日期
    date_options = ['DATE', 'TIME', '日期', 'INDEX']
    date_col = next((c for c in df.columns if any(k in c for k in date_options)), None)
    if date_col:
        res['Date_Final'] = pd.to_datetime(df[date_col], errors='coerce')

    # 六大因子映射邏輯
    map_dict = {
        'SP500': ['SP500', 'VOO', 'PRICE', '收盤', 'CLOSE'],
        'SP500EW': ['RSP', 'EW', '等權重'],
        'HY_SPREAD': ['SPREAD', 'HY_SPREAD', '利差'],
        'TIPS_10Y': ['TIPS', 'TIPS_10Y', '實質利率'],
        'VIX': ['VIX', '恐慌', '^VIX'],
        'CAPE': ['CAPE', '席勒', '本益比']
    }

    for target, keywords in map_dict.items():
        for col in df.columns:
            if any(k in col for k in keywords) and target not in res.columns:
                res[target] = pd.to_numeric(
                    df[col].astype(str).str.replace(',', '').str.replace('$', ''), 
                    errors='coerce'
                )
                break

    # 強制 Close = SP500 同步
    if 'SP500' in res.columns:
        res['Close'] = res['SP500']

    # 補回其餘所有因子
    for col in df.columns:
        if col not in list(res.columns) + [date_col]:
            res[col] = df[col]

    return res.dropna(subset=['Date_Final'])

def get_web_data(start_d, end_d):
    """獲取 VOO/VIX 最新補丁數據"""
    try:
        spy = yf.Ticker("SPY").history(start=start_d, end=end_d, interval="1wk")
        vix = yf.Ticker("^VIX").history(start=start_d, end=end_d, interval="1wk")
        for d in [spy, vix]:
            if not d.empty: d.index = d.index.tz_localize(None)
        w_df = pd.DataFrame(index=spy.index)
        w_df['SP500_Web'] = spy['Close']
        w_df['VIX_Web'] = vix['Close']
        w_df.index.name = 'Date_Final'
        return w_df.reset_index()
    except Exception as e:
        st.warning(f"聯網補強異常: {str(e)}")
        return pd.DataFrame()

# ==========================================
# 3. 側邊欄：1000 萬資產配置
# ==========================================
st.sidebar.header("💰 1. 資產配置 (核心1000萬)")
TOTAL_W = st.sidebar.number_input("總資產 (萬 NTD)", value=1000)
T_CAP = TOTAL_W * 10000

CASH_W = st.sidebar.number_input("現金預備金 (萬 NTD)", value=200)
C_RSV = CASH_W * 10000

D_POOL = T_CAP - C_RSV # 800萬 DCA 池
base_dca_w = st.sidebar.number_input("月 DCA 基數 (萬 NTD)", value=20)
B_DCA = base_dca_w * 10000

st.sidebar.header("🛡️ 2. 熔斷自定義")
M_LOSS = st.sidebar.slider("帳面虧損熔斷 (%)", -30, -5, -15) / 100
M_SMA = st.sidebar.number_input("均線週數", value=200)
M_VIX = st.sidebar.slider("VIX 恐慌門檻", 20, 60, 40)

st.sidebar.header("⚙️ 3. 買進訊號")
R_PERIOD = st.sidebar.number_input("RSI 週期", value=14)
R_LV1 = st.sidebar.slider("超賣爆買 RSI (4x)", 20, 45, 35)
R_LV2 = st.sidebar.slider("提速加碼 RSI (2x)", 30, 55, 45)

up_file = st.sidebar.file_uploader("📥 4. 上傳 CSV", type=['csv'])

# ==========================================
# 4. 數據加載流程 (多行防截斷架構)
# ==========================================
if st.sidebar.button("🚀 執行強力數據對齊", type="primary"):
    web_df = get_web_data(date(2003, 5, 1), date.today())
    if up_file:
        df_csv = normalize_factors(pd.read_csv(up_file))
        # 徹底解決重複欄位與標籤
        df_csv = df_csv.loc[:, ~df_csv.columns.duplicated()].copy()
        df_csv = df_csv.drop_duplicates(subset=['Date_Final'])
        
        if not web_df.empty:
            web_df = web_df.drop_duplicates(subset=['Date_Final'])
            final = pd.merge(web_df, df_csv, on='Date_Final', how='outer')
        else:
            final = df_csv
            
        # 因子補齊
        for f in ['SP500', 'VIX']:
            w_c = f + "_Web"
            if w_c in final.columns:
                if f not in final.columns: final[f] = final[w_c]
                else: final[f] = final[f].combine_first(final[w_c])
        
        final['Close'] = final['SP500']
        # 逐一刪除 Web 欄位，避免一行代碼過長
        web_list = [c for c in final.columns if '_Web' in c]
        final = final.drop(columns=web_list)
        # 顯式重命名
        final = final.rename(columns={'Date_Final': 'Date'})
    else:
        if web_df.empty: st.stop()
        final = web_df.rename(columns={'Date_Final': 'Date', 'SP500_Web': 'SP500', 'VIX_Web': 'VIX'})
        final['Close'] = final['SP500']
    
    # 全局排序與填充
    final = final.copy().sort_values('Date').ffill()
    st.session_state['master_df'] = final.dropna(subset=['Date', 'Close'])
    st.success("✅ 數據載入成功")

# ==========================================
# 5. 主介面：監控與回測
# ==========================================
if 'master_df' not in st.session_state:
    st.info("💡 請上傳 CSV 或執行數據整合啟動分析")
    st.stop()

df = st.session_state['master_df'].copy()
df['RSI'] = get_rsi(df['Close'], R_PERIOD)
df['SMA'] = df['Close'].rolling(window=M_SMA, min_periods=1).mean()
df['DD'] = (df['Close'] - df['Close'].rolling(window=52, min_periods=1).max()) / df['Close'].rolling(window=52, min_periods=1).max()

tab1, tab2 = st.tabs(["📊 即時監控", "⏳ 歷史回測"])

with tab1:
    latest = df.iloc[-1]
    st.subheader(f"數據基準日: {latest['Date'].strftime('%Y-%m-%d')}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("VOO 價格", f"${latest['Close']:.2f}")
    c2.metric("RSI", f"{latest['RSI']:.1f}")
    c3.metric("VIX 指數", f"{latest.get('VIX', 0):.1f}")
    c4.metric("高點回撤", f"{latest['DD']:.1%}")

    st.markdown("---")
    u_cost = st.number_input("您的持倉成本 (VOO)", value=450.0)
    u_loss = (latest['Close'] - u_cost) / u_cost if u_cost > 0 else 0
    
    # 熔斷邏輯
    is_m = u_loss < M_LOSS or latest['Close'] < latest['SMA'] or latest.get('VIX', 0) > M_VIX

    if is_m: st.error("🔴 目前狀態：熔斷模式啟動 (暫停扣款)")
    else:
        if latest['RSI'] < R_LV1: st.warning(f"🔥 超賣階段：加碼爆買 ({B_DCA*4/10000:.0f}萬)")
        elif latest['RSI'] < R_LV2: st.warning(f"🟡 提速階段：兩倍扣款 ({B_DCA*2/10000:.0f}萬)")
        else: st.success(f"🔵 正常階段：基礎 DCA ({B_DCA/10000:.0f}萬)")
    st.dataframe(df.tail(10))

with tab2:
    st.subheader("1000 萬資產策略績效報告")
    # 初始化資金容器
    sh, d_pool, r_pool, cur_m, hist = 0, D_POOL, C_RSV, -1, []
    bh_sh = T_CAP / df['Close'].iloc[0]
    r_flags = {'r15': False, 'r25': False, 'r35': False}
    
    for i, row in df.iterrows():
        p, dd = row['Close'], row['DD']
        # 帳面計算
        ac = (T_CAP - d_pool - r_pool) / sh if sh > 0 else 0
        l_bt = (p - ac) / ac if ac > 0 else 0
        
        # 200萬預備金抄底 (15/25/35%)
        for tr, k in [(-0.15, 'r15'), (-0.25, 'r25'), (-0.35, 'r35')]:
            if dd <= tr and not r_flags[k] and r_pool >= C_RSV * 0.3:
                inv = C_RSV * 0.3 if tr > -0.35 else r_pool
                sh += inv / p; r_pool -= inv; r_flags[k] = True
        if dd >= 0: r_flags = {key: False for key in r_flags}
        
        # 每月階梯 DCA (消耗 800萬池)
        if row['Date'].month != cur_m:
            cur_m = row['Date'].month
            melt = l_bt < M_LOSS or p < row['SMA'] or row.get('VIX', 0) > M_VIX
            amt = 0
            if not melt:
                if row['RSI'] < R_LV1: amt = B_DCA * 4
                elif row['RSI'] < R_LV2: amt = B_DCA * 2
                else: amt = B_DCA
            if amt > 0 and d_pool >= amt:
                d_pool -= amt; sh += amt / p
        
        hist.append({'Date': row['Date'], 'Strategy': sh * p + d_pool + r_pool, 'BH': bh_sh * p})
    
    res_df = pd.DataFrame(hist).set_index('Date')
    st.line_chart(res_df)
    
    def calc_metrics(v_ser):
        tr = (v_ser.iloc[-1] - T_CAP) / T_CAP
        y = len(v_ser) / 52
        cagr = (v_ser.iloc[-1] / T_CAP) ** (1 / y) - 1 if y > 0 else 0
        mdd = ((v_ser - v_ser.cummax()) / v_ser.cummax()).min()
        rets = v_ser.pct_change(fill_method=None).dropna()
        sharpe = (cagr - 0.02) / (rets.std() * np.sqrt(52)) if rets.std() > 0 else 0
        return [f"{tr:.2%}", f"{cagr:.2%}", f"{mdd:.2%}", f"{sharpe:.2f}"]
    
    perf = pd.DataFrame({"指標": ["總報酬", "年化報酬", "最大回撤", "夏普值"],
                         "矛與盾策略": calc_metrics(res_df['Strategy']),
                         "Buy & Hold": calc_metrics(res_df['BH'])})
    st.table(perf)

st.markdown("---")
st.caption("v9.10 Modular Edition | 針對雲端部署環境優化")
