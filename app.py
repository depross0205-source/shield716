import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, date

# ==========================================
# 1. 系統初始化與版本防護
# ==========================================
st.set_page_config(page_title="矛與盾 7.80 終極版", page_icon="🛡️", layout="wide")
st.title("🛡️ 矛與盾 7.80 終極量化系統 ⚔️")

def safe_divider():
    """修復 Streamlit 1.19.0 不支援 divider 的問題"""
    try: st.divider()
    except: st.markdown("---")

# ==========================================
# 2. 數據清洗與因子對齊
# ==========================================
def normalize_factors(df):
    """【需求 1 & 4】識別因子並保留所有數據，Close 參照 SP500"""
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
    # 尋找日期並轉換
    date_col = next((c for c in df.columns if any(k in c for k in ['DATE', 'TIME', '日期', 'INDEX'])), None)
    if date_col:
        res['Date_Final'] = pd.to_datetime(df[date_col], errors='coerce')
    
    # 識別核心因子
    for target, kws in mapping.items():
        for col in df.columns:
            if any(kw in col for kw in kws) and target not in res.columns:
                res[target] = pd.to_numeric(df[col].astype(str).str.replace(',', '').str.replace('$', ''), errors='coerce')
                break
    
    # 【核心需求】Close 參照 SP500 數字，而不是替代
    if 'SP500' in res.columns:
        res['Close'] = res['SP500']
    
    # 保留所有其餘欄位 (Spread, TIPS 等)
    for col in df.columns:
        if col not in list(res.columns) + [date_col]:
            res[col] = df[col]
            
    return res.dropna(subset=['Date_Final'])

def get_web_data(start_date, end_date):
    """聯網獲取最新數據作為補丁"""
    try:
        spy = yf.Ticker("SPY").history(start=start_date, end=end_date, interval="1wk")
        rsp = yf.Ticker("RSP").history(start=start_date, end=end_date, interval="1wk")
        vix = yf.Ticker("^VIX").history(start=start_date, end=end_date, interval="1wk")
        for d in [spy, rsp, vix]:
            if not d.empty: d.index = d.index.tz_localize(None)
        
        web_df = pd.DataFrame(index=spy.index)
        web_df['SP500_Web'] = spy['Close'] * 0.9 # 模擬 VOO 級別
        web_df['SP500EW_Web'] = rsp['Close']
        web_df['VIX_Web'] = vix['Close']
        web_df.index.name = 'Date_Final'
        return web_df.reset_index()
    except:
        return pd.DataFrame()

# ==========================================
# 3. 側邊欄：【需求 2 & 3】參數與 1000 萬資金
# ==========================================
st.sidebar.header("💰 1. 資金分配 (1000萬核心)")
total_inv = st.sidebar.number_input("總投資預算 (NTD)", value=10000000)
reserve_cash = st.sidebar.number_input("現金預備金 (抄底專用)", value=2000000)
# 剩餘資金用於 DCA
dca_avail = total_inv - reserve_cash
st.sidebar.info(f"可用於定期定額 (DCA) 資金：{dca_avail/10000:.0f} 萬")
base_dca_amt = st.sidebar.number_input("每月基礎 DCA 金額 (NTD)", value=200000)

st.sidebar.header("🛡️ 2. 自定義熔斷設定")
with st.sidebar.expander("熔斷門檻調整", expanded=True):
    melt_loss_limit = st.slider("帳面虧損熔斷 (%)", -30, -5, -15) / 100
    melt_sma_period = st.number_input("熔斷參考均線 (週)", value=200, min_value=10)
    melt_vix_limit = st.slider("VIX 恐慌熔斷門檻", 20, 60, 40)

st.sidebar.header("⚙️ 3. RSI 買進訊號設定")
# 【修復 NameError】確保變數定義在最外層
rsi_p = st.sidebar.number_input("RSI 計算週期 (週)", value=14)
confirm_w = st.sidebar.slider("訊號連續確認週數", 1, 5, 1)
with st.sidebar.expander("RSI 觸發階梯設定"):
    rsi_speed = st.slider("加速 (2x) RSI 門檻", 30, 55, 45)
    rsi_extra = st.slider("超賣加碼 (4x) RSI 門檻", 20, 45, 35)
    rsi_melt_buy = st.slider("熔斷中允許加碼 RSI", 10, 40, 30)

up_file = st.sidebar.file_uploader("📥 4. 上傳 CSV 資料庫 (優先採用)", type=['csv'])

# ==========================================
# 4. 數據整合流程 (CSV 優先 -> 聯網更新 -> 前週沿用)
# ==========================================
if st.sidebar.button("🚀 執行數據強力整合與分析", type="primary"):
    web_df = get_web_data(date(2003, 5, 1), date.today())
    
    if up_file:
        df_csv = normalize_factors(pd.read_csv(up_file))
        # 移除重複標籤
        df_csv = df_csv.drop_duplicates(subset=['Date_Final'])
        web_df = web_df.drop_duplicates(subset=['Date_Final'])
        # 合併：以 CSV 為主，Web 補入新日期
        final = pd.merge(web_df, df_csv, on='Date_Final', how='outer')
        for f in ['SP500', 'SP500EW', 'VIX']:
            web_col = f"{f}_Web"
            if f not in final.columns: final[f] = final[web_col]
            else: final[f] = final[f].combine_first(final[web_col])
        final['Close'] = final['SP500']
        final = final.drop(columns=['SP500_Web', 'SP500EW_Web', 'VIX_Web']).rename(columns={'Date_Final': 'Date'})
    else:
        final = web_df.rename(columns={'Date_Final': 'Date', 'SP500_Web': 'SP500', 'SP500_Web': 'Close', 'SP500EW_Web': 'SP500EW', 'VIX_Web': 'VIX'})

    # 【需求 4】一律沿用前一週數據 (ffill) 並排重
    final = final.loc[:, ~final.columns.duplicated()].sort_values('Date').ffill().dropna(subset=['Date', 'Close'])
    st.session_state['master_data'] = final

# ==========================================
# 5. 主介面：監控面板與回測引擎
# ==========================================
if 'master_data' in st.session_state:
    df = st.session_state['master_data'].copy()
    
    # 指標計算
    def get_rsi(s, p=14):
        d = s.diff(); g = d.where(d > 0, 0); l = -d.where(d < 0, 0)
        ag = g.ewm(com=p-1, min_periods=p).mean(); al = l.ewm(com=p-1, min_periods=p).mean()
        return 100 - (100 / (1 + (ag / (al + 1e-9))))
    
    df['RSI_Final'] = get_rsi(df['Close'], rsi_p)
    df['SMA_Melt'] = df['Close'].rolling(window=melt_sma_period, min_periods=1).mean()
    df['Drawdown'] = (df['Close'] - df['Close'].rolling(window=52, min_periods=1).max()) / df['Close'].rolling(window=52, min_periods=1).max()
    
    # 訊號確認邏輯
    df['S_Sig'] = (df['RSI_Final'] < rsi_speed).rolling(window=confirm_w).sum() == confirm_w
    df['E_Sig'] = (df['RSI_Final'] < rsi_extra).rolling(window=confirm_w).sum() == confirm_w
    df['M_Sig'] = (df['RSI_Final'] < rsi_melt_buy).rolling(window=confirm_w).sum() == confirm_w

    tab1, tab2 = st.tabs(["📊 實時監控面板", "⏳ 策略回測報告"])

    with tab1:
        latest = df.iloc[-1]
        st.subheader(f"數據更新日：{latest['Date'].strftime('%Y-%m-%d')}")
        
        avg_cost = st.number_input("您的 VOO 平均持倉成本", value=450.0)
        p_loss = (latest['Close'] - avg_cost) / avg_cost
        
        # 熔斷判定
        is_melt = (p_loss < melt_loss_limit) or (latest['Close'] < latest['SMA_Melt']) or (latest['VIX'] > melt_vix_limit)
        
        c = st.columns(4)
        c[0].metric("最新價格", f"${latest['Close']:.2f}")
        c[1].metric("目前 RSI", f"{latest['RSI_Final']:.1f}")
        c[2].metric("VIX 指數", f"{latest['VIX']:.1f}")
        c[3].metric("距高回撤", f"{latest['Drawdown']:.1%}")

        safe_divider()
        if is_melt:
            st.error(f"🔴 目前狀態：熔斷模式啟動 (虧損 < {melt_loss_limit:.0%} 或 價 < SMA{melt_sma_period} 或 VIX > {melt_vix_limit})")
            if latest['M_Sig']: st.warning(f"💡 補丁加碼：RSI 低於 {rsi_melt_buy}，可單次投入 {base_dca_amt*2/10000:.0f} 萬")
        else:
            if latest['E_Sig']: st.warning(f"🔥 目前狀態：超賣爆買 ({base_dca_amt*4/10000:.0f} 萬)")
            elif latest['S_Sig']: st.warning(f"🟡 目前狀態：加速扣款 ({base_dca_amt*2/10000:.0f} 萬)")
            else: st.success(f"🔵 目前狀態：基礎定期定額 ({base_dca_amt/10000:.0f} 萬)")
        
        st.write("### 數據全因子預覽：")
        st.dataframe(df.tail(10))

    with tab2:
        st.subheader("策略績效 v.s. 大盤 B&H (1000萬資金模型)")
        # 回測變數
        shares, dca_p, rsv_p, curr_m, hist = 0, dca_avail, reserve_cash, -1, []
        bh_shares = total_inv / df['Close'].iloc[0]
        r15 = r25 = r35 = False

        for i, row in df.iterrows():
            p, r, dd, s_s, e_s, m_s, v, sma = row['Close'], row['RSI_Final'], row['Drawdown'], row['S_Sig'], row['E_Sig'], row['M_Sig'], row['VIX'], row['SMA_Melt']
            ac_bt = (total_inv - dca_p - rsv_p) / shares if shares > 0 else 0
            loss_bt = (p - ac_bt) / ac_bt if ac_bt > 0 else 0
            
            # 預備金抄底 (15/25/35)
            for trg, flag in [(-0.35, 'r35'), (-0.25, 'r25'), (-0.15, 'r15')]:
                if dd <= trg and not locals()[flag] and rsv_p >= reserve_cash * 0.3:
                    inv = reserve_cash * 0.3 if trg > -0.35 else rsv_p
                    shares += inv/p; rsv_p -= inv; exec(f"{flag}=True")
            if dd >= 0: r15 = r25 = r35 = False

            # 每月定期定額
            if row['Date'].month != curr_m:
                curr_m = row['Date'].month
                is_m_bt = (loss_bt < melt_loss_limit) or (p < sma) or (v > melt_vix_limit)
                amt = 0
                if is_m_bt: amt = base_dca_amt * 2 if m_s else 0
                else: amt = base_dca_amt * 4 if e_s else (base_dca_amt * 2 if s_s else base_dca_amt)
                if amt > 0 and dca_p >= amt: dca_p -= amt; shares += amt/p
            
            hist.append({'Date': row['Date'], 'Strategy': (shares*p)+dca_p+rsv_p, 'BH': bh_shares*p})

        res_df = pd.DataFrame(hist).set_index('Date')
        st.line_chart(res_df)
        
        # 績效指標計算
        def calculate_metrics(values, initial_funds):
            returns = values.pct_change().dropna()
            total_return = (values.iloc[-1] - initial_funds) / initial_funds
            cagr = (values.iloc[-1]/initial_funds)**(1/(len(values)/52)) - 1
            mdd = ((values - values.cummax())/values.cummax()).min()
            sharpe = (cagr - 0.02) / (returns.std() * np.sqrt(52))
            return [f"{total_return:.2%}", f"{cagr:.2%}", f"{mdd:.2%}", f"{sharpe:.2f}", f"{returns.std()*np.sqrt(52):.2%}"]

        perf = pd.DataFrame({
            "指標": ["總報酬率", "年化報酬 (CAGR)", "最大回撤 (MDD)", "夏普指數", "年化標準差"],
            "矛與盾策略": calculate_metrics(res_df['Strategy'], total_inv),
            "Buy & Hold": calculate_metrics(res_df['BH'], total_inv)
        })
        st.table(perf)
else:
    st.info("請上傳 CSV 資料庫並點擊「執行強力數據整合與分析」開始。")
