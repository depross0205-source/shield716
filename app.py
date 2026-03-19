import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, date

# ==========================================
# 1. 系統環境相容性設定
# ==========================================
st.set_page_config(page_title="矛與盾 7.70 終極版", page_icon="🛡️", layout="wide")
st.title("🛡️ 矛與盾 7.70 全功能量化系統 ⚔️")

def safe_divider():
    """修復 Streamlit 1.19.0 不支援 divider 的問題"""
    try: st.divider()
    except: st.markdown("---")

# ==========================================
# 2. 數據清洗與因子對齊函數
# ==========================================
def normalize_factors(df):
    """強力識別因子，保留所有原始數據"""
    if df.empty: return df
    df = df.reset_index()
    df.columns = [str(c).strip().upper() for c in df.columns]
    
    # 模糊匹配字典
    mapping = {
        'SP500': ['SP500', 'VOO', 'CLOSE', 'PRICE', '價格', '收盤'],
        'SP500EW': ['RSP', 'EW', '等權重', 'SP500EW'],
        'HY_Spread': ['SPREAD', 'HY_SPREAD', '利差'],
        'TIPS_10Y': ['TIPS', 'TIPS_10Y', '實質利率'],
        'Vix': ['VIX', '恐慌', '^VIX'],
        'Cape': ['CAPE', '席勒', '本益比']
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
    
    # 確保 Close 參照 SP500 數值
    if 'SP500' in res.columns: res['Close'] = res['SP500']
    
    # 補回所有未被標記的原始因子
    for col in df.columns:
        if col not in list(res.columns) + [date_col]:
            res[col] = df[col]
            
    return res.dropna(subset=['Date_Final'])

def get_web_data(start_d, end_d):
    """獲取最新聯網補丁數據"""
    try:
        spy = yf.Ticker("SPY").history(start=start_d, end=end_d, interval="1wk")
        rsp = yf.Ticker("RSP").history(start=start_d, end=end_d, interval="1wk")
        vix = yf.Ticker("^VIX").history(start=start_d, end=end_d, interval="1wk")
        for d in [spy, rsp, vix]:
            if not d.empty: d.index = d.index.tz_localize(None)
        
        web_df = pd.DataFrame(index=spy.index)
        web_df['SP500_Web'] = spy['Close'] * 0.9 # VOO 換算比率
        web_df['SP500EW_Web'] = rsp['Close']
        web_df['Vix_Web'] = vix['Close']
        web_df.index.name = 'Date_Final'
        return web_df.reset_index()
    except:
        return pd.DataFrame()

# ==========================================
# 3. 側邊欄：資金與策略參數
# ==========================================
st.sidebar.header("💰 1. 資金分配 (1000萬核心)")
total_inv = st.sidebar.number_input("總投資預算 (NTD)", value=10000000)
reserve_cash = st.sidebar.number_input("現金預備金 (抄底專用)", value=2000000)
dca_avail = total_inv - reserve_cash
st.sidebar.info(f"可用於定期定額 (DCA) 資金：{dca_avail/10000:.0f} 萬")

base_dca_amt = st.sidebar.number_input("每月基礎 DCA 金額", value=200000)

st.sidebar.header("⚙️ 2. 策略參數設定")
confirm_w = st.sidebar.slider("訊號連續確認週數", 1, 5, 1)
with st.sidebar.expander("RSI 門檻細項"):
    rsi_speed = st.slider("加速 (2x) RSI 門檻", 30, 55, 45)
    rsi_extra = st.slider("加碼 (40萬) RSI 門檻", 20, 45, 35)
    rsi_melt = st.slider("熔斷 (暫停) RSI 門檻", 10, 40, 30)

up_file = st.sidebar.file_uploader("📥 3. 上傳 CSV 資料庫", type=['csv'])

# ==========================================
# 4. 數據整合引擎 (CSV 優先 + 自動補強)
# ==========================================
if st.sidebar.button("🚀 執行強力數據對齊", type="primary"):
    web_df = get_web_data(date(2003, 5, 1), date.today())
    if up_file:
        df_csv = normalize_factors(pd.read_csv(up_file))
        final = pd.merge(web_df, df_csv, on='Date_Final', how='outer')
        for f in ['SP500', 'SP500EW', 'Vix']:
            web_c = f"{f}_Web"
            if f not in final.columns: final[f] = final[web_c]
            else: final[f] = final[f].combine_first(final[web_c])
        final['Close'] = final['SP500']
        final = final.drop(columns=['SP500_Web', 'SP500EW_Web', 'Vix_Web']).rename(columns={'Date_Final': 'Date'})
    else:
        final = web_df.rename(columns={'Date_Final': 'Date', 'SP500_Web': 'SP500', 'SP500_Web': 'Close', 'SP500EW_Web': 'SP500EW', 'Vix_Web': 'Vix'})

    # 沿用前週數據 (ffill)
    final = final.sort_values('Date').ffill().dropna(subset=['Date', 'Close'])
    st.session_state['master'] = final

# ==========================================
# 5. 主介面顯示 (監控與回測)
# ==========================================
if 'master' in st.session_state:
    # 計算指標
    df = st.session_state['master'].copy()
    def get_rsi(s, p=14):
        d = s.diff(); g = d.where(d > 0, 0); l = -d.where(d < 0, 0)
        ag = g.ewm(com=p-1, min_periods=p).mean(); al = l.ewm(com=p-1, min_periods=p).mean()
        return 100 - (100 / (1 + (ag / (al + 1e-9))))
    
    df['RSI'] = get_rsi(df['Close'])
    df['SMA200'] = df['Close'].rolling(window=200, min_periods=1).mean()
    df['DD'] = (df['Close'] - df['Close'].rolling(window=52, min_periods=1).max()) / df['Close'].rolling(window=52, min_periods=1).max()
    
    # 訊號判定 (連續確認)
    df['S_Sig'] = (df['RSI'] < rsi_speed).rolling(window=confirm_w).sum() == confirm_w
    df['E_Sig'] = (df['RSI'] < rsi_extra).rolling(window=confirm_w).sum() == confirm_w
    df['M_Sig'] = (df['RSI'] < rsi_melt).rolling(window=confirm_w).sum() == confirm_w

    t1, t2 = st.tabs(["📊 即時監控面板", "⏳ 策略回測引擎"])

    with t1:
        latest = df.iloc[-1]
        st.subheader(f"數據基準日：{latest['Date'].strftime('%Y-%m-%d')}")
        
        # 判定目前階段
        current_cost = st.number_input("您的平均持有成本", value=450.0)
        p_loss = (latest['Close'] - current_cost) / current_cost
        is_melt = (p_loss < -0.15) or (latest['Close'] < latest['SMA200']) or (latest['Vix'] > 40)
        
        status_cols = st.columns(4)
        status_cols[0].metric("最新價格", f"${latest['Close']:.2f}")
        status_cols[1].metric("目前 RSI", f"{latest['RSI']:.1f}")
        status_cols[2].metric("VIX 指數", f"{latest['Vix']:.1f}")
        status_cols[3].metric("距高回撤", f"{latest['DD']:.1%}")

        safe_divider()
        if is_melt:
            st.error("🔴 目前階段：熔斷啟動中 (暫停定期定額)")
            if latest['M_Sig']: st.warning(f"💡 補丁觸發：RSI < {rsi_melt}，允許單次加碼 {base_dca_amt*2/10000:.0f} 萬")
        else:
            if latest['E_Sig']: st.warning(f"🔥 目前階段：超賣爆買 (每月 {base_dca_amt*4/10000:.0f} 萬)")
            elif latest['S_Sig']: st.warning(f"🟡 目前階段：提速扣款 (每月 {base_dca_amt*2/10000:.0f} 萬)")
            else: st.success(f"🔵 目前階段：基礎扣款 (每月 {base_dca_amt/10000:.0f} 萬)")

    with t2:
        # 回測邏輯
        st.subheader("策略歷史績效 v.s. 大盤持有 (B&H)")
        shares, core_p, rsv_p, ac_bt, curr_m, hist = 0, dca_avail, reserve_cash, 0, -1, []
        r15 = r25 = r35 = False
        bh_shares = total_inv / df['Close'].iloc[0]

        for i, row in df.iterrows():
            p, r, dd, s_sig, e_sig, m_sig, v, sma = row['Close'], row['RSI'], row['DD'], row['S_Sig'], row['E_Sig'], row['M_Sig'], row['Vix'], row['SMA200']
            ac_bt = (total_inv - core_p - rsv_p) / shares if shares > 0 else 0
            p_loss_bt = (p - ac_bt) / ac_bt if ac_bt > 0 else 0
            
            # 現金預備金抄底 (15%/25%/35%)
            for trg, flag in [(-0.35, 'r35'), (-0.25, 'r25'), (-0.15, 'r15')]:
                if dd <= trg and not locals()[flag] and rsv_p >= reserve_cash * 0.3:
                    inv = reserve_cash * 0.3 if trg > -0.35 else rsv_p
                    shares += inv/p; rsv_p -= inv; exec(f"{flag}=True")
            if dd >= 0: r15 = r25 = r35 = False

            # 每月定額
            if row['Date'].month != curr_m:
                curr_m = row['Date'].month
                melt_bt = (p_loss_bt < -0.15) or (p < sma) or (v > 40)
                amt = 0
                if melt_bt: amt = base_dca_amt * 2 if m_sig else 0
                else: amt = base_dca_amt * 4 if e_sig else (base_dca_amt * 2 if s_sig else base_dca_amt)
                if amt > 0 and core_p >= amt: core_p -= amt; shares += amt/p
            
            hist.append({'Date': row['Date'], 'Strategy': (shares*p)+core_p+rsv_p, 'BH': bh_shares*p})
        
        res = pd.DataFrame(hist).set_index('Date')
        st.line_chart(res)
        
        # 績效表
        def get_metrics(v, initial):
            rets = v.pct_change().dropna()
            total_ret = (v.iloc[-1] - initial) / initial
            ann_ret = (v.iloc[-1]/initial)**(1/(len(v)/52)) - 1
            mdd = ((v - v.cummax())/v.cummax()).min()
            sharpe = (ann_ret - 0.02) / (rets.std() * np.sqrt(52))
            return [f"{total_ret:.2%}", f"{ann_ret:.2%}", f"{mdd:.2%}", f"{sharpe:.2f}"]

        perf = pd.DataFrame({
            "指標": ["總報酬率", "年化報酬", "最大回測 (MDD)", "夏普指數"],
            "矛與盾策略": get_metrics(res['Strategy'], total_inv),
            "Buy & Hold": get_metrics(res['BH'], total_inv)
        })
        st.table(perf)
else:
    st.info("請上傳 CSV 資料庫並點擊「執行強力數據對齊」開始。")
