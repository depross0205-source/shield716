import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, date

# ==========================================
# 1. 系統初始化與相容性
# ==========================================
st.set_page_config(page_title="矛與盾 8.10 終極穩定版", page_icon="🛡️", layout="wide")
st.title("🛡️ 矛與盾 8.10 終極量化系統 ⚔️")

def safe_divider():
    try: st.divider()
    except: st.markdown("---")

# ==========================================
# 2. 數據對齊函數 (確保核心因子不遺失)
# ==========================================
def normalize_factors(df):
    if df.empty: return df
    df = df.reset_index()
    df.columns = [str(c).strip().upper() for c in df.columns]
    
    mapping = {
        'SP500': ['SP500', 'VOO', 'PRICE', '價格', '收盤', 'CLOSE'],
        'SP500EW': ['RSP', 'EW', '等權重', 'SP500EW'],
        'HY_Spread': ['SPREAD', 'HY_SPREAD', '利差'],
        'TIPS_10Y': ['TIPS', 'TIPS_10Y', '實質利率'],
        'VIX': ['VIX', '恐慌', '^VIX'],
        'CAPE': ['CAPE', '席勒', '本益比']
    }
    
    res = pd.DataFrame()
    date_col = next((c for c in df.columns if any(k in c for k in ['DATE', 'TIME', '日期', 'INDEX'])), None)
    if date_col:
        res['Date_Final'] = pd.to_datetime(df[date_col], errors='coerce')
    
    for target, kws in mapping.items():
        for col in df.columns:
            if any(kw in col for kw in kws) and target not in res.columns:
                res[target] = pd.to_numeric(df[col].astype(str).str.replace(',', '').str.replace('$', ''), errors='coerce')
                break
    
    if 'SP500' in res.columns: res['Close'] = res['SP500']
    
    for col in df.columns:
        if col not in list(res.columns) + [date_col]:
            res[col] = df[col]
            
    return res.dropna(subset=['Date_Final'])

def get_web_patch(start_date, end_date):
    try:
        spy = yf.Ticker("SPY").history(start=start_date, end=end_date, interval="1wk")
        rsp = yf.Ticker("RSP").history(start=start_date, end=end_date, interval="1wk")
        vix = yf.Ticker("^VIX").history(start=start_date, end=end_date, interval="1wk")
        for d in [spy, rsp, vix]:
            if not d.empty: d.index = d.index.tz_localize(None)
        
        web_df = pd.DataFrame(index=spy.index)
        web_df['SP500_Web'] = spy['Close'] * 0.9 
        web_df['SP500EW_Web'] = rsp['Close']
        web_df['VIX_Web'] = vix['Close']
        web_df.index.name = 'Date_Final'
        return web_df.reset_index()
    except:
        return pd.DataFrame()

# ==========================================
# 3. 側邊欄：全局參數定義 (防護 NameError)
# ==========================================
st.sidebar.header("💰 1. 資金分配中心")
TOTAL_CAP = st.sidebar.number_input("總資金 (NTD)", value=10000000)
CASH_RSV = st.sidebar.number_input("抄底預備金 (NTD)", value=2000000)
DCA_POOL = TOTAL_CAP - CASH_RSV

BASE_DCA = st.sidebar.number_input("基礎 DCA 基數", value=200000)

st.sidebar.header("🛡️ 2. 熔斷機制設定")
M_LOSS = st.sidebar.slider("虧損門檻 (%)", -30, -5, -15) / 100
M_SMA = st.sidebar.number_input("均線週數", value=200)
M_VIX = st.sidebar.slider("VIX 門檻", 20, 60, 40)

st.sidebar.header("⚙️ 3. RSI 訊號參數")
RSI_P = st.sidebar.number_input("RSI 週期", value=14)
CONF_W = st.sidebar.slider("連續確認週數", 1, 5, 1)

with st.sidebar.expander("加碼門檻設定"):
    R_SPEED = st.slider("提速 (2x)", 30, 55, 45)
    R_EXTRA = st.slider("爆買 (4x)", 20, 45, 35)
    R_MELT_BUY = st.slider("熔斷抄底 RSI", 10, 40, 30)

up_file = st.sidebar.file_uploader("📥 4. 上傳 CSV 資料庫", type=['csv'])

# ==========================================
# 4. 數據整合引擎
# ==========================================
if st.sidebar.button("🚀 執行數據對齊與分析", type="primary"):
    web_df = get_web_patch(date(2003, 5, 1), date.today())
    if up_file:
        df_csv = normalize_factors(pd.read_csv(up_file))
        df_csv = df_csv.drop_duplicates(subset=['Date_Final'])
        web_df = web_df.drop_duplicates(subset=['Date_Final'])
        final = pd.merge(web_df, df_csv, on='Date_Final', how='outer')
        for f in ['SP500', 'SP500EW', 'VIX']:
            web_col = f"{f}_Web"
            if f not in final.columns: final[f] = final[web_col]
            else: final[f] = final[f].combine_first(final[web_col])
        final['Close'] = final['SP500']
        final = final.drop(columns=['SP500_Web', 'SP500EW_Web', 'VIX_Web']).rename(columns={'Date_Final': 'Date'})
    else:
        final = web_df.rename(columns={'Date_Final': 'Date', 'SP500_Web': 'SP500', 'SP500_Web': 'Close', 'SP500EW_Web': 'SP500EW', 'VIX_Web': 'VIX'})

    final = final.loc[:, ~final.columns.duplicated()].sort_values('Date').ffill().dropna(subset=['Date', 'Close'])
    st.session_state['master_data'] = final

# ==========================================
# 5. 主介面顯示 (監控與強化回測)
# ==========================================
if 'master_data' in st.session_state:
    data = st.session_state['master_data'].copy()
    
    # 計算指標
    def get_rsi(s, p=14):
        d = s.diff(); g = d.where(d > 0, 0); l = -d.where(d < 0, 0)
        ag = g.ewm(com=p-1, min_periods=p).mean(); al = l.ewm(com=p-1, min_periods=p).mean()
        return 100 - (100 / (1 + (ag / (al + 1e-9))))
    
    data['RSI_C'] = get_rsi(data['Close'], RSI_P)
    data['SMA_M'] = data['Close'].rolling(window=M_SMA, min_periods=1).mean()
    data['DD'] = (data['Close'] - data['Close'].rolling(window=52, min_periods=1).max()) / data['Close'].rolling(window=52, min_periods=1).max()
    
    data['S_Sig'] = (data['RSI_C'] < R_SPEED).rolling(window=CONF_W).sum() == CONF_W
    data['E_Sig'] = (data['RSI_C'] < R_EXTRA).rolling(window=CONF_W).sum() == CONF_W
    data['M_Sig'] = (data['RSI_C'] < R_MELT_BUY).rolling(window=CONF_W).sum() == CONF_W

    t1, t2 = st.tabs(["📊 實時監控", "⏳ 策略回測"])

    with t1:
        latest = data.iloc[-1]
        st.subheader(f"基準日：{latest['Date'].strftime('%Y-%m-%d')}")
        cost_in = st.number_input("平均持倉成本", value=450.0)
        p_loss = (latest['Close'] - cost_in) / cost_in
        is_melt = (p_loss < M_LOSS) or (latest['Close'] < latest['SMA_M']) or (latest['VIX'] > M_VIX)
        
        c = st.columns(4)
        c[0].metric("最新價格", f"${latest['Close']:.2f}"); c[1].metric("RSI", f"{latest['RSI_C']:.1f}")
        c[2].metric("VIX", f"{latest['VIX']:.1f}"); c[3].metric("回撤", f"{latest['DD']:.1%}")

        safe_divider()
        if is_melt:
            st.error("🔴 目前狀態：熔斷暫停中")
            if latest['M_Sig']: st.warning(f"💡 抄底提醒：RSI 達標，可單次加碼 {BASE_DCA*2/10000:.0f} 萬")
        else:
            if latest['E_Sig']: st.warning(f"🔥 超賣爆買 ({BASE_DCA*4/10000:.0f} 萬)"); 
            elif latest['S_Sig']: st.warning(f"🟡 提速扣款 ({BASE_DCA*2/10000:.0f} 萬)"); 
            else: st.success(f"🔵 基礎扣款 ({BASE_DCA/10000:.0f} 萬)")
        st.dataframe(data.tail(5))

    with t2:
        st.subheader("策略歷史回測 (1000 萬資產模型)")
        # 核心回測參數初始化
        shares, cur_dca_p, cur_rsv_p, cur_m, hist = 0, DCA_POOL, CASH_RSV, -1, []
        bh_shares = TOTAL_CAP / data['Close'].iloc[0]
        # 用字典管理旗標，徹底解決 locals() 當掉問題
        flags = {'r15': False, 'r25': False, 'r35': False}

        for i, row in data.iterrows():
            p, dd, v, sma = row['Close'], row['DD'], row['VIX'], row['SMA_M']
            ac_bt = (TOTAL_CAP - cur_dca_p - cur_rsv_p) / shares if shares > 0 else 0
            loss_bt = (p - ac_bt) / ac_bt if ac_bt > 0 else 0
            
            # 預備金抄底 (15/25/35%)
            for trg, f_key in [(-0.15, 'r15'), (-0.25, 'r25'), (-0.35, 'r35')]:
                if dd <= trg and not flags[f_key] and cur_rsv_p >= CASH_RSV * 0.3:
                    inv = CASH_RSV * 0.3 if trg > -0.35 else cur_rsv_p
                    shares += inv/p; cur_rsv_p -= inv; flags[f_key] = True
            if dd >= 0: flags = {k: False for k in flags} # 回升後重置

            # 每月階梯 DCA
            if row['Date'].month != cur_m:
                cur_m = row['Date'].month
                melt_bt = (loss_bt < M_LOSS) or (p < sma) or (v > M_VIX)
                amt = 0
                if melt_bt: amt = BASE_DCA * 2 if row['M_Sig'] else 0
                else: amt = BASE_DCA * 4 if row['E_Sig'] else (BASE_DCA * 2 if row['S_Sig'] else BASE_DCA)
                if amt > 0 and cur_dca_p >= amt: cur_dca_p -= amt; shares += amt/p
            
            hist.append({'Date': row['Date'], 'Strategy': (shares*p)+cur_dca_p+cur_rsv_p, 'BH': bh_shares*p})

        res_v = pd.DataFrame(hist).set_index('Date')
        st.line_chart(res_v)
        
        def metrics(v, init):
            r = v.pct_change().dropna(); tr = (v.iloc[-1] - init) / init
            ann = (v.iloc[-1]/init)**(1/(len(v)/52)) - 1
            md = ((v - v.cummax())/v.cummax()).min()
            sh = (ann - 0.02) / (r.std() * np.sqrt(52))
            return [f"{tr:.2%}", f"{ann:.2%}", f"{md:.2%}", f"{sh:.2f}"]

        perf = pd.DataFrame({"指標": ["總報酬率", "年化報酬", "最大回撤", "夏普指數"],
                             "矛與盾策略": metrics(res_v['Strategy'], TOTAL_CAP),
                             "Buy & Hold": metrics(res_v['BH'], TOTAL_CAP)})
        st.table(perf)
