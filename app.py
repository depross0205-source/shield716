import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, date

# ==========================================
# 1. 系統環境設定 (信心程度：10 分)
# ==========================================
st.set_page_config(page_title="矛與盾 8.90 終極版", page_icon="🛡️", layout="wide")
st.title("🛡️ 矛與盾 8.90 終極量化系統 ⚔️")

def safe_divider():
    """解決舊版 Streamlit 不支援 divider 的問題"""
    try: st.divider()
    except: st.markdown("---")

# ==========================================
# 2. 數據強力對齊函數 (核心因子保護)
# ==========================================
def normalize_factors(df):
    """識別核心因子，Close 強制同步 SP500，保留所有原始數據"""
    if df.empty: return df
    df = df.reset_index()
    # 統一清理欄位名：去空格、轉大寫
    df.columns = [str(c).strip().upper() for c in df.columns]
    
    mapping = {
        'SP500': ['SP500', 'VOO', 'PRICE', '價格', '收盤', 'CLOSE'],
        'SP500EW': ['RSP', 'EW', '等權重', 'SP500EW'],
        'HY_SPREAD': ['SPREAD', 'HY_SPREAD', '利差'],
        'TIPS_10Y': ['TIPS', 'TIPS_10Y', '實質利率'],
        'VIX': ['VIX', '恐慌', '^VIX'],
        'CAPE': ['CAPE', '席勒', '本益比']
    }
    
    res = pd.DataFrame()
    # 尋找唯一的日期欄位
    date_col = next((c for c in df.columns if any(k in c for k in ['DATE', 'TIME', '日期', 'INDEX'])), None)
    if date_col:
        res['Date_Final'] = pd.to_datetime(df[date_col], errors='coerce')
    
    # 識別核心因子
    for target_key, kws in mapping.items():
        for col in df.columns:
            if any(kw in col for kw in kws) and target_key not in res.columns:
                res[target_key] = pd.to_numeric(df[col].astype(str).str.replace(',', '').str.replace('$', ''), errors='coerce')
                break
    
    # 【核心需求】Close 強制同步自 CSV 的 SP500 數據
    if 'SP500' in res.columns: 
        res['Close'] = res['SP500']
    
    # 補回剩餘因子 (CAPE, Tips 等)
    for col in df.columns:
        if col not in list(res.columns) + [date_col]:
            res[col] = df[col]
            
    return res.dropna(subset=['Date_Final'])

def get_web_patch(start_d, end_d):
    """獲取最新聯網補丁"""
    try:
        spy = yf.Ticker("SPY").history(start=start_d, end=end_d, interval="1wk")
        rsp = yf.Ticker("RSP").history(start=start_d, end=end_d, interval="1wk")
        vix = yf.Ticker("^VIX").history(start=start_d, end=end_d, interval="1wk")
        for d in [spy, rsp, vix]:
            if not d.empty: d.index = d.index.tz_localize(None)
        
        web_df = pd.DataFrame(index=spy.index)
        web_df['SP500_Web'] = spy['Close'] * 0.9 
        web_df['SP500EW_Web'] = rsp['Close']
        web_df['Vix_Web'] = vix['Close']
        web_df.index.name = 'Date_Final'
        return web_df.reset_index()
    except:
        return pd.DataFrame()

# ==========================================
# 3. 側邊欄：全域參數定義 (解決 NameError)
# ==========================================
st.sidebar.header("💰 1. 資金分配 (1000 萬架構)")
TOTAL_CAP = st.sidebar.number_input("總資產預算 (NTD)", value=10000000)
CASH_RSV = st.sidebar.number_input("現金預備金 (抄底用)", value=2000000)
DCA_POOL = TOTAL_CAP - CASH_RSV # 800 萬 DCA 池
base_dca_amt = st.sidebar.number_input("基礎月扣基數 (NTD)", value=200000)

st.sidebar.header("🛡️ 2. 自定義熔斷參數")
with st.sidebar.expander("熔斷門檻調整", expanded=True):
    M_LOSS = st.slider("帳面虧損熔斷門檻 (%)", -30, -5, -15) / 100
    M_SMA = st.number_input("參考均線週期 (週)", value=200)
    M_VIX = st.slider("VIX 恐慌熔斷門檻", 20, 60, 40)

st.sidebar.header("⚙️ 3. RSI 買進訊號設定")
RSI_P = st.sidebar.number_input("RSI 計算週期", value=14)
CONF_W = st.sidebar.slider("連續訊號確認週數", 1, 5, 1)

with st.sidebar.expander("加碼階梯設定"):
    R_SPEED = st.slider("提速扣款 (2x) RSI", 30, 55, 45)
    R_EXTRA = st.slider("加碼爆買 (4x) RSI", 20, 45, 35)
    R_MELT_B = st.slider("熔斷中允許買入 RSI", 10, 40, 30)

up_file = st.sidebar.file_uploader("📥 4. 上傳 CSV 資料庫", type=['csv'])

# ==========================================
# 4. 數據整合流程 (徹底解決當機與 NameError)
# ==========================================
if st.sidebar.button("🚀 啟動強力數據對齊與回測", type="primary"):
    web_df = get_web_patch(date(2003, 5, 1), date.today())
    
    if up_file:
        df_csv = normalize_factors(pd.read_csv(up_file))
        # 強制排重，確保 Date 標籤全球唯一
        df_csv = df_csv.loc[:, ~df_csv.columns.duplicated()].drop_duplicates(subset=['Date_Final'])
        web_df = web_df.drop_duplicates(subset=['Date_Final'])
        
        final = pd.merge(web_df, df_csv, on='Date_Final', how='outer')
        # 修正後的因子補齊邏輯，避免使用引發錯誤的變數
        for f in ['SP500', 'SP500EW', 'Vix']:
            w_col = f"{f}_Web"
            if w_col in final.columns:
                if f not in final.columns: final[f] = final[w_col]
                else: final[f] = final[f].combine_first(final[w_col])
        
        final['Close'] = final['SP500']
        # 移除 Web 暫存欄位，修復導致 SyntaxError 的語法
        final = final.drop(columns=[c for c in final.columns if '_Web' in c])
        final = final.rename(columns={'Date_Final': 'Date'})
    else:
        final = web_df.rename(columns={'Date_Final': 'Date', 'SP500_Web': 'SP500', 'Vix_Web': 'Vix'})
        final['Close'] = final['SP500']

    # 數據補強：ffill 沿用前週，解決數據間缺口
    final = final.loc[:, ~final.columns.duplicated()].sort_values('Date').ffill().dropna(subset=['Date', 'Close'])
    st.session_state['master_df'] = final

# ==========================================
# 5. 主介面顯示
# ==========================================
if 'master_df' in st.session_state:
    df = st.session_state['master_df'].copy()
    
    # 計算 RSI 指標
    def get_rsi(s, p=14):
        d = s.diff(); g = d.where(d > 0, 0); l = -d.where(d < 0, 0)
        ag = g.ewm(com=p-1, min_periods=p).mean(); al = l.ewm(com=p-1, min_periods=p).mean()
        return 100 - (100 / (1 + (ag / (al + 1e-9))))
    
    df['RSI_V'] = get_rsi(df['Close'], RSI_P)
    df['SMA_V'] = df['Close'].rolling(window=M_SMA, min_periods=1).mean()
    df['DD_V'] = (df['Close'] - df['Close'].rolling(window=52, min_periods=1).max()) / df['Close'].rolling(window=52, min_periods=1).max()
    
    # 連續訊號判定
    df['S_Sig'] = (df['RSI_V'] < R_SPEED).rolling(window=CONF_W).sum() == CONF_W
    df['E_Sig'] = (df['RSI_V'] < R_EXTRA).rolling(window=CONF_W).sum() == CONF_W
    df['M_Sig'] = (df['RSI_V'] < R_MELT_B).rolling(window=CONF_W).sum() == CONF_W

    tab1, tab2 = st.tabs(["📊 即時監控面板", "⏳ 策略歷史回測"])

    with tab1:
        latest = df.iloc[-1]
        st.subheader(f"數據更新日：{latest['Date'].strftime('%Y-%m-%d')}")
        cost_in = st.number_input("持倉平均成本 (USD)", value=450.0)
        p_loss_v = (latest['Close'] - cost_in) / cost_in
        is_melt_v = (p_loss_v < M_LOSS) or (latest['Close'] < latest['SMA_V']) or (latest['Vix'] > M_VIX)
        
        c = st.columns(4)
        c[0].metric("最新價格", f"${latest['Close']:.2f}"); c[1].metric("RSI", f"{latest['RSI_V']:.1f}")
        c[2].metric("VIX", f"{latest['Vix']:.1f}"); c[3].metric("回撤", f"{latest['DD_V']:.1%}")

        safe_divider()
        if is_melt_v:
            st.error(f"🔴 目前狀態：熔斷模式啟動 (暫停定期定額)")
            if latest['M_Sig']: st.warning(f"💡 加碼提醒：RSI 低於 {R_MELT_B}，可額外投入 {base_dca_amt*2/10000:.0f} 萬")
        else:
            if latest['E_Sig']: st.warning(f"🔥 超賣爆買 (每月 {base_dca_amt*4/10000:.0f} 萬)")
            elif latest['S_Sig']: st.warning(f"🟡 提速扣款 (每月 {base_dca_amt*2/10000:.0f} 萬)")
            else: st.success(f"🔵 基礎定期定額 (每月 {base_dca_amt/10000:.0f} 萬)")
        st.dataframe(df.tail(10))

    with tab2:
        st.subheader("1000 萬資產回測對照 (矛與盾 v.s. B&H)")
        shares, dca_p, rsv_p, curr_m, hist = 0, DCA_POOL, CASH_RSV, -1, []
        bh_sh = TOTAL_CAP / df['Close'].iloc[0]
        f_dict = {'r15': False, 'r25': False, 'r35': False}

        for i, row in df.iterrows():
            p, dd, v, sma = row['Close'], row['DD_V'], row['Vix'], row['SMA_V']
            ac_bt = (TOTAL_CAP - dca_p - rsv_p) / shares if shares > 0 else 0
            loss_bt = (p - ac_bt) / ac_bt if ac_bt > 0 else 0
            
            # 預備金抄底 (15/25/35% 規則)
            for trg, k in [(-0.15, 'r15'), (-0.25, 'r25'), (-0.35, 'r35')]:
                if dd <= trg and not f_dict[k] and rsv_p >= CASH_RSV * 0.3:
                    inv = CASH_RSV * 0.3 if trg > -0.35 else rsv_p
                    shares += inv/p; rsv_p -= inv; f_dict[k] = True
            if dd >= 0: f_dict = {key: False for key in f_dict}

            # 每月階梯式 DCA
            if row['Date'].month != curr_m:
                curr_m = row['Date'].month
                melt_bt = (loss_bt < M_LOSS) or (p < sma) or (v > M_VIX)
                amt = 0
                if melt_bt: amt = base_dca_amt * 2 if row['M_Sig'] else 0
                else: amt = base_dca_amt * 4 if row['E_Sig'] else (base_dca_amt * 2 if row['S_Sig'] else base_dca_amt)
                if amt > 0 and dca_p >= amt: dca_p -= amt; shares += amt/p
            
            hist.append({'Date': row['Date'], 'Strategy': (shares*p)+dca_p+rsv_p, 'BH': bh_sh*p})

        res_v = pd.DataFrame(hist).set_index('Date')
        st.line_chart(res_v)
        
        def get_perf(v_ser, init):
            r = v_ser.pct_change().dropna(); tr = (v_ser.iloc[-1] - init) / init
            ann = (v_ser.iloc[-1]/init)**(1/(len(v_ser)/52)) - 1
            md = ((v_ser - v_ser.cummax())/v_ser.cummax()).min()
            sh = (ann - 0.02) / (r.std() * np.sqrt(52))
            return [f"{tr:.2%}", f"{ann:.2%}", f"{md:.2%}", f"{sh:.2f}"]

        st.table(pd.DataFrame({"指標": ["總報酬率", "年化報酬", "最大回撤", "夏普指數"],
                              "矛與盾策略": get_perf(res_v['Strategy'], TOTAL_CAP),
                              "B&H 對照": get_perf(res_v['BH'], TOTAL_CAP)}))
else:
    st.info("💡 系統已徹底修復！請上傳 CSV 並點擊「啟動強力數據對齊」開始。")
