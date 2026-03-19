import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, date

# ==========================================
# 1. 系統環境相容性 (解決 st.divider 問題)
# ==========================================
st.set_page_config(page_title="矛與盾 7.90 終極版", page_icon="🛡️", layout="wide")
st.title("🛡️ 矛與盾 7.90 終極數據整合系統 ⚔️")

def safe_divider():
    try: st.divider()
    except: st.markdown("---")

# ==========================================
# 2. 數據清洗與因子對齊 (保留所有因子)
# ==========================================
def normalize_factors(df):
    """強力識別關鍵因子，Close 強制參考 SP500"""
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
    # 尋找日期
    date_col = next((c for c in df.columns if any(k in c for k in ['DATE', 'TIME', '日期', 'INDEX'])), None)
    if date_col:
        res['Date_Final'] = pd.to_datetime(df[date_col], errors='coerce')
    
    # 識別核心因子
    for target, kws in mapping.items():
        for col in df.columns:
            if any(kw in col for kw in kws) and target not in res.columns:
                res[target] = pd.to_numeric(df[col].astype(str).str.replace(',', '').str.replace('$', ''), errors='coerce')
                break
    
    # 【核心需求】Close 同步 SP500 數字，不替代
    if 'SP500' in res.columns: res['Close'] = res['SP500']
    
    # 補回剩餘所有原始欄位 (Spread, Cape等)
    for col in df.columns:
        if col not in list(res.columns) + [date_col]:
            res[col] = df[col]
            
    return res.dropna(subset=['Date_Final'])

def get_web_data(start_date, end_date):
    """聯網獲取最新數據 (SPY, RSP, ^VIX)"""
    try:
        spy = yf.Ticker("SPY").history(start=start_date, end=end_date, interval="1wk")
        rsp = yf.Ticker("RSP").history(start=start_date, end=end_date, interval="1wk")
        vix = yf.Ticker("^VIX").history(start=start_date, end=end_date, interval="1wk")
        for d in [spy, rsp, vix]:
            if not d.empty: d.index = d.index.tz_localize(None)
        
        web_df = pd.DataFrame(index=spy.index)
        web_df['SP500_Web'] = spy['Close'] * 0.9 # VOO 換算比例
        web_df['SP500EW_Web'] = rsp['Close']
        web_df['VIX_Web'] = vix['Close']
        web_df.index.name = 'Date_Final'
        return web_df.reset_index()
    except:
        return pd.DataFrame()

# ==========================================
# 3. 側邊欄：資金分配與策略參數
# ==========================================
st.sidebar.header("💰 1. 資金分配 (1000萬架構)")
total_invest = st.sidebar.number_input("總投資額度 (NTD)", value=10000000)
cash_reserve = st.sidebar.number_input("現金預備金 (抄底專用)", value=2000000)
dca_fund_pool = total_invest - cash_reserve
st.sidebar.info(f"可用於定期定額 (DCA) 資金：{dca_fund_pool/10000:.0f} 萬")

base_dca = st.sidebar.number_input("基礎月扣額度 (NTD)", value=200000)

st.sidebar.header("🛡️ 2. 熔斷自定義")
with st.sidebar.expander("熔斷參數調整", expanded=True):
    m_loss_limit = st.slider("帳面虧損門檻 (%)", -30, -5, -15) / 100
    m_sma_period = st.number_input("均線過濾週期 (週)", value=200)
    m_vix_limit = st.slider("VIX 恐慌門檻", 20, 60, 40)

st.sidebar.header("⚙️ 3. RSI 訊號參數")
# 【修復重點】確保變數定義在全局作用域
rsi_period = st.sidebar.number_input("RSI 週期", value=14)
conf_weeks = st.sidebar.slider("連續訊號確認週數", 1, 5, 1)
with st.sidebar.expander("RSI 階梯門檻"):
    rsi_speed = st.slider("提速門檻 (2x)", 30, 55, 45)
    rsi_extra = st.slider("爆買門檻 (4x)", 20, 45, 35)
    rsi_m_buy = st.slider("熔斷中加碼門檻", 10, 40, 30)

up_file = st.sidebar.file_uploader("📥 4. 上傳 CSV 資料庫", type=['csv'])

# ==========================================
# 4. 數據整合引擎 (CSV 優先 -> 聯網補點 -> 前週沿用)
# ==========================================
if st.sidebar.button("🚀 執行強力數據對齊與回測", type="primary"):
    web_df = get_web_data(date(2003, 5, 1), date.today())
    if up_file:
        df_csv = normalize_factors(pd.read_csv(up_file))
        # 移除標籤衝突
        df_csv = df_csv.drop_duplicates(subset=['Date_Final'])
        web_df = web_df.drop_duplicates(subset=['Date_Final'])
        # 外部合併保留所有因子
        final = pd.merge(web_df, df_csv, on='Date_Final', how='outer')
        for f in ['SP500', 'SP500EW', 'VIX']:
            web_c = f"{f}_Web"
            if f not in final.columns: final[f] = final[web_c]
            else: final[f] = final[f].combine_first(final[web_c])
        final['Close'] = final['SP500']
        final = final.drop(columns=['SP500_Web', 'SP500EW_Web', 'VIX_Web']).rename(columns={'Date_Final': 'Date'})
    else:
        final = web_df.rename(columns={'Date_Final': 'Date', 'SP500_Web': 'SP500', 'SP500_Web': 'Close', 'SP500EW_Web': 'SP500EW', 'VIX_Web': 'VIX'})

    # 【需求 4】前週數據沿用 (ffill)
    final = final.loc[:, ~final.columns.duplicated()].sort_values('Date').ffill().dropna(subset=['Date', 'Close'])
    st.session_state['master_state'] = final

# ==========================================
# 5. 分頁：即時監控面板 & 策略回測引擎
# ==========================================
if 'master_state' in st.session_state:
    df = st.session_state['master_state'].copy()
    
    # 指標計算
    def calculate_rsi(s, p=14):
        d = s.diff(); g = d.where(d > 0, 0); l = -d.where(d < 0, 0)
        ag = g.ewm(com=p-1, min_periods=p).mean(); al = l.ewm(com=p-1, min_periods=p).mean()
        return 100 - (100 / (1 + (ag / (al + 1e-9))))

    df['RSI_V'] = calculate_rsi(df['Close'], rsi_period)
    df['SMA_V'] = df['Close'].rolling(window=m_sma_period, min_periods=1).mean()
    df['DD_V'] = (df['Close'] - df['Close'].rolling(window=52, min_periods=1).max()) / df['Close'].rolling(window=52, min_periods=1).max()
    
    # 訊號確認
    df['S_Sig'] = (df['RSI_V'] < rsi_speed).rolling(window=conf_weeks).sum() == conf_weeks
    df['E_Sig'] = (df['RSI_V'] < rsi_extra).rolling(window=conf_weeks).sum() == conf_weeks
    df['M_Sig'] = (df['RSI_V'] < rsi_m_buy).rolling(window=conf_weeks).sum() == conf_weeks

    tab1, tab2 = st.tabs(["📊 即時監控", "⏳ 策略回測"])

    with tab1:
        latest = df.iloc[-1]
        st.subheader(f"數據更新日：{latest['Date'].strftime('%Y-%m-%d')}")
        cost_in = st.number_input("輸入您的持倉成本", value=450.0)
        p_loss_v = (latest['Close'] - cost_in) / cost_in
        is_melt_v = (p_loss_v < m_loss_limit) or (latest['Close'] < latest['SMA_V']) or (latest['VIX'] > m_vix_limit)
        
        c = st.columns(4)
        c[0].metric("最新價格", f"${latest['Close']:.2f}"); c[1].metric("RSI", f"{latest['RSI_V']:.1f}"); c[2].metric("VIX", f"{latest['VIX']:.1f}"); c[3].metric("回撤", f"{latest['DD_V']:.1%}")

        safe_divider()
        if is_melt_v:
            st.error(f"🔴 目前階段：熔斷模式啟動 (暫停扣款)")
            if latest['M_Sig']: st.warning(f"💡 抄底訊號：RSI < {rsi_m_buy}，建議加碼 {base_dca*2/10000:.0f} 萬")
        else:
            if latest['E_Sig']: st.warning(f"🔥 目前階段：超賣爆買 ({base_dca*4/10000:.0f} 萬)")
            elif latest['S_Sig']: st.warning(f"🟡 目前階段：提速扣款 ({base_dca*2/10000:.0f} 萬)")
            else: st.success(f"🟢 目前階段：基礎扣款 ({base_dca/10000:.0f} 萬)")
        
        st.write("### 因子預覽："); st.dataframe(df.tail(10))

    with tab2:
        st.subheader("策略績效對比 (1000萬模型)")
        shares, dca_p, rsv_p, curr_m, hist = 0, dca_fund_pool, cash_reserve, -1, []
        bh_sh = total_invest / df['Close'].iloc[0]
        r15 = r25 = r35 = False

        for i, row in df.iterrows():
            p, r, dd, v, sma = row['Close'], row['RSI_V'], row['DD_V'], row['VIX'], row['SMA_V']
            ac_bt = (total_invest - dca_p - rsv_p) / shares if shares > 0 else 0
            p_loss_bt = (p - ac_bt) / ac_bt if ac_bt > 0 else 0
            
            # 現金預備金抄底 (15/25/35)
            for trg, flg in [(-0.35, 'r35'), (-0.25, 'r25'), (-0.15, 'r15')]:
                if dd <= trg and not locals()[flg] and rsv_p >= cash_reserve * 0.3:
                    inv = cash_reserve * 0.3 if trg > -0.35 else rsv_p
                    shares += inv/p; rsv_p -= inv; exec(f"{flg}=True")
            if dd >= 0: r15 = r25 = r35 = False

            # 每月定期定額
            if row['Date'].month != curr_m:
                curr_m = row['Date'].month
                melt_bt = (p_loss_bt < m_loss_limit) or (p < sma) or (v > m_vix_limit)
                amt = 0
                if melt_bt: amt = base_dca * 2 if row['M_Sig'] else 0
                else: amt = base_dca * 4 if row['E_Sig'] else (base_dca * 2 if row['S_Sig'] else base_dca)
                if amt > 0 and dca_p >= amt: dca_p -= amt; shares += amt/p
            
            hist.append({'Date': row['Date'], 'Strategy': (shares*p)+dca_p+rsv_p, 'BH': bh_sh*p})

        res_v = pd.DataFrame(hist).set_index('Date')
        st.line_chart(res_v)
        
        def metrics(vals, initial):
            re = vals.pct_change().dropna()
            tr = (vals.iloc[-1] - initial) / initial
            ann = (vals.iloc[-1]/initial)**(1/(len(vals)/52)) - 1
            md = ((vals - vals.cummax())/vals.cummax()).min()
            sh = (ann - 0.02) / (re.std() * np.sqrt(52))
            return [f"{tr:.2%}", f"{ann:.2%}", f"{md:.2%}", f"{sh:.2f}", f"{re.std()*np.sqrt(52):.2%}"]

        p_tab = pd.DataFrame({"指標": ["總報酬率", "年化報酬", "最大回測", "夏普指數", "年化標差"],
                              "矛與盾": metrics(res_v['Strategy'], total_invest),
                              "Buy&Hold": metrics(res_v['BH'], total_invest)})
        st.table(p_tab)
else:
    st.info("💡 操作指南：1. 上傳 CSV 資料庫 2. 點擊「執行強力數據對齊與回測」。")
