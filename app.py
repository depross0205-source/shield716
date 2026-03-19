import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import traceback
from datetime import datetime, date

# ==========================================
# 1. 系統基礎配置
# ==========================================
st.set_page_config(page_title="矛與盾 10.00", page_icon="🛡️", layout="wide")
st.title("🛡️ 矛與盾 v10.00 破壁者終極系統 ⚔️")

# ==========================================
# 2. 核心運算與因子保護模組
# ==========================================
def get_rsi(s, period=14):
    """計算 RSI 數值，加入 1e-9 防止除以零崩潰"""
    delta = s.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_g = gain.ewm(com=period-1, min_periods=period).mean()
    avg_l = loss.ewm(com=period-1, min_periods=period).mean()
    rs = avg_g / (avg_l + 1e-9)
    return 100 - (100 / (1 + rs))

def normalize_factors(df):
    """【換個思考方向】防止欄位互相吞噬的安全對齊模組"""
    if df.empty: return df
    df = df.reset_index()
    df.columns = [str(c).strip().upper() for c in df.columns]
    res = pd.DataFrame()

    d_col = next((c for c in df.columns if any(k in c for k in ['DATE', 'TIME', '日期', 'INDEX'])), None)
    if d_col:
        res['Date_Final'] = pd.to_datetime(df[d_col], errors='coerce')

    # 注意順序：先比對 SP500EW，再比對 SP500，防止誤判
    m = {
        'SP500EW': ['RSP', 'EW', '等權重', 'SP500EW'],
        'SP500': ['SP500', 'VOO', 'PRICE', '收盤', 'CLOSE'],
        'HY_SPREAD': ['SPREAD', 'HY_SPREAD', '利差'],
        'TIPS_10Y': ['TIPS', 'TIPS_10Y', '實質利率'],
        'VIX': ['VIX', '恐慌', '^VIX'],
        'CAPE': ['CAPE', '席勒', '本益比']
    }

    available_cols = list(df.columns)
    for target, kws in m.items():
        for col in list(available_cols):
            if any(k in col for k in kws):
                res[target] = pd.to_numeric(
                    df[col].astype(str).str.replace(',', '').str.replace('$', ''), errors='coerce'
                )
                available_cols.remove(col) # 鎖定已配對的欄位
                break

    if 'SP500' in res.columns:
        res['Close'] = res['SP500']

    # 補回所有剩餘未配對的欄位
    for col in available_cols:
        if col != d_col: res[col] = df[col]

    return res.dropna(subset=['Date_Final'])

def get_web_data(start_d, end_d):
    """獲取網路數據 (加入錯誤防護)"""
    try:
        s = yf.Ticker("SPY").history(start=start_d, end=end_d, interval="1wk")
        v = yf.Ticker("^VIX").history(start=start_d, end=end_d, interval="1wk")
        for d in [s, v]:
            if not d.empty: d.index = d.index.tz_localize(None)
        w_df = pd.DataFrame(index=s.index)
        w_df['SP500_Web'] = s['Close']
        w_df['VIX_Web'] = v['Close']
        w_df.index.name = 'Date_Final'
        return w_df.reset_index()
    except Exception:
        return pd.DataFrame()

# ==========================================
# 3. 側邊欄：1000 萬資產配置
# ==========================================
st.sidebar.header("💰 1. 資產配置 (核心1000萬)")
T_W = st.sidebar.number_input("總資產 (萬 NTD)", value=1000)
T_CAP = T_W * 10000

C_W = st.sidebar.number_input("現金預備金 (萬 NTD)", value=200)
C_RSV = C_W * 10000

D_POOL = T_CAP - C_RSV # 800萬 DCA 池
b_dca_w = st.sidebar.number_input("月 DCA 基數 (萬 NTD)", value=20)
B_DCA = b_dca_w * 10000

st.sidebar.header("🛡️ 2. 熔斷自定義")
M_LOSS = st.sidebar.slider("帳面虧損熔斷 (%)", -30, -5, -15) / 100
M_SMA = st.sidebar.number_input("均線週數", value=200)
M_VIX = st.sidebar.slider("VIX 恐慌門檻", 20, 60, 40)

st.sidebar.header("⚙️ 3. 買進訊號")
R_P = st.sidebar.number_input("RSI 週期", value=14)
R_LV1 = st.sidebar.slider("超賣爆買 RSI (4x)", 20, 45, 35)
R_LV2 = st.sidebar.slider("提速加碼 RSI (2x)", 30, 55, 45)

up_file = st.sidebar.file_uploader("📥 4. 上傳 CSV", type=['csv'])

# ==========================================
# 4. 數據加載流程 (加入 Try-Except 探測器)
# ==========================================
if st.sidebar.button("🚀 執行強力數據對齊", type="primary"):
    try:
        web_df = get_web_data(date(2003, 5, 1), date.today())
        
        if up_file:
            up_file.seek(0) # 【打破鬼打牆的關鍵】：重置指標，防止讀到空文件
            raw_df = pd.read_csv(up_file)
            if raw_df.empty: raise ValueError("讀取到的 CSV 為空，請檢查檔案。")
            
            df_csv = normalize_factors(raw_df)
            df_csv = df_csv.loc[:, ~df_csv.columns.duplicated()].copy()
            df_csv = df_csv.drop_duplicates(subset=['Date_Final'])
            
            if not web_df.empty:
                web_df = web_df.drop_duplicates(subset=['Date_Final'])
                final = pd.merge(web_df, df_csv, on='Date_Final', how='outer')
            else:
                final = df_csv
                
            for f in ['SP500', 'VIX']:
                w_c = f"{f}_Web"
                if w_c in final.columns:
                    if f not in final.columns: final[f] = final[w_c]
                    else: final[f] = final[f].combine_first(final[w_c])
            
            if 'SP500' not in final.columns:
                raise ValueError("無法找到大盤(SP500)數據，無法進行回測。")
                
            final['Close'] = final['SP500']
            final = final.drop(columns=[c for c in final.columns if '_Web' in c])
            final = final.rename(columns={'Date_Final': 'Date'})
        else:
            if web_df.empty: raise ValueError("未上傳 CSV 且網路獲取失敗，無法進行分析。")
            final = web_df.rename(columns={'Date_Final': 'Date', 'SP500_Web': 'SP500', 'VIX_Web': 'VIX'})
            final['Close'] = final['SP500']
        
        final = final.copy().sort_values('Date').ffill()
        final = final.dropna(subset=['Date', 'Close'])
        
        if final.empty: raise ValueError("對齊後無有效數據，請檢查上傳資料的日期區間。")
            
        st.session_state['master_df'] = final
        st.success("✅ 數據載入成功！請查看右側面板。")
        
    except Exception as e:
        st.error(f"❌ 數據整合失敗: {str(e)}")
        st.code(traceback.format_exc())
        st.stop()

# ==========================================
# 5. 主介面：監控與回測 (加入全域防護罩)
# ==========================================
if 'master_df' not in st.session_state:
    st.info("💡 請上傳 CSV 或執行數據整合啟動分析")
    st.stop()

try:
    df = st.session_state['master_df'].copy()
    df['RSI'] = get_rsi(df['Close'], R_P)
    df['SMA'] = df['Close'].rolling(window=M_SMA, min_periods=1).mean()
    # 改用 cummax() 確保 MDD 計算絕對正確
    df['DD'] = (df['Close'] - df['Close'].cummax()) / df['Close'].cummax()

    t1, t2 = st.tabs(["📊 即時監控", "⏳ 歷史回測"])

    with t1:
        l = df.iloc[-1]
        st.subheader(f"基準日: {l['Date'].strftime('%Y-%m-%d')}")
        c = st.columns(4)
        c[0].metric("大盤價格", f"${l['Close']:.2f}")
        c[1].metric("RSI", f"{l['RSI']:.1f}")
        
        v_val = l.get('VIX', 0)
        v_val = 0 if pd.isna(v_val) else v_val
        c[2].metric("VIX 指數", f"{v_val:.1f}")
        c[3].metric("歷史回撤", f"{l['DD']:.1%}")

        st.markdown("---")
        u_cost = st.number_input("您的持倉成本", value=450.0)
        u_loss = (l['Close'] - u_cost) / u_cost if u_cost > 0 else 0
        
        is_m = u_loss < M_LOSS or l['Close'] < l['SMA'] or v_val > M_VIX

        if is_m: st.error("🔴 狀態：熔斷模式啟動 (暫停常規扣款)")
        else:
            if l['RSI'] < R_LV1: st.warning(f"🔥 超賣階段：加碼爆買 ({B_DCA*4/10000:.0f}萬)")
            elif l['RSI'] < R_LV2: st.warning(f"🟡 提速階段：兩倍扣款 ({B_DCA*2/10000:.0f}萬)")
            else: st.success(f"🔵 正常階段：基礎 DCA ({B_DCA/10000:.0f}萬)")
        st.dataframe(df.tail(10))

    with t2:
        st.subheader("1000 萬資產策略績效報告")
        sh, d_p, r_p, c_m, hist = 0, D_POOL, C_RSV, -1, []
        bh_sh = T_CAP / df['Close'].iloc[0] if df['Close'].iloc[0] > 0 else 0
        flags = {'r15': False, 'r25': False, 'r35': False}
        
        for i, row in df.iterrows():
            p, dd = row['Close'], row['DD']
            ac = (T_CAP - d_p - r_p) / sh if sh > 0 else 0
            l_bt = (p - ac) / ac if ac > 0 else 0
            
            # 防護 NaN 比較
            v_val_bt = row.get('VIX', 0)
            v_val_bt = 0 if pd.isna(v_val_bt) else v_val_bt
            
            # 200萬預備金抄底
            for tr, k in [(-0.15, 'r15'), (-0.25, 'r25'), (-0.35, 'r35')]:
                if dd <= tr and not flags[k] and r_p >= C_RSV * 0.3:
                    inv = C_RSV * 0.3 if tr > -0.35 else r_p
                    sh += inv / p; r_p -= inv; flags[k] = True
            if dd >= 0: flags = {key: False for key in flags}
            
            # 每月階梯 DCA (消耗 800萬池)
            if row['Date'].month != c_m:
                c_m = row['Date'].month
                melt = l_bt < M_LOSS or p < row['SMA'] or v_val_bt > M_VIX
                amt = 0
                if not melt:
                    if row['RSI'] < R_LV1: amt = B_DCA * 4
                    elif row['RSI'] < R_LV2: amt = B_DCA * 2
                    else: amt = B_DCA
                if amt > 0 and d_p >= amt:
                    d_p -= amt; sh += amt / p
            
            hist.append({'Date': row['Date'], 'Strategy': sh * p + d_p + r_p, 'BH': bh_sh * p})
        
        res_df = pd.DataFrame(hist).set_index('Date')
        st.line_chart(res_df)
        
        def calc_metrics(v_ser):
            tr = (v_ser.iloc[-1] - T_CAP) / T_CAP
            y = max(len(v_ser) / 52.0, 1.0) # 修正短回測年化報酬炸裂問題
            cagr = (v_ser.iloc[-1] / T_CAP) ** (1 / y) - 1
            mdd = ((v_ser - v_ser.cummax()) / v_ser.cummax()).min()
            rets = v_ser.pct_change(fill_method=None).dropna()
            shrp = (cagr - 0.02) / (rets.std() * np.sqrt(52)) if rets.std() > 0 else 0
            return [f"{tr:.2%}", f"{cagr:.2%}", f"{mdd:.2%}", f"{shrp:.2f}"]
        
        perf = pd.DataFrame({"指標": ["總報酬", "年化報酬", "最大回撤", "夏普值"],
                             "矛與盾策略": calc_metrics(res_df['Strategy']),
                             "Buy & Hold": calc_metrics(res_df['BH'])})
        st.table(perf)

except Exception as e:
    st.error(f"❌ 系統運算中發生錯誤: {str(e)}")
    st.code(traceback.format_exc())
    st.info("💡 如果你看到這個錯誤，請將其截圖，這能精準定位問題。")

st.markdown("---")
st.caption("v10.00 Ghost Wall Breaker | 加入物理級記憶體防護與探測器")
