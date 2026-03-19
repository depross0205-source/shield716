import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, date

# ==========================================

# 1. 系統基礎配置 (防禦性架構)

# ==========================================

st.set_page_config(page_title=“Spear and Shield”, page_icon=“🛡️”, layout=“wide”)
st.title(“🛡️ 矛與盾 數據精確回歸系統 ⚔️”)

# ==========================================

# 2. 核心運算函數 (恢復正確的數學邏輯)

# ==========================================

def get_rsi(s, period=14):
“”“計算 RSI 數值”””
delta = s.diff()
gain = delta.where(delta > 0, 0)
loss = -delta.where(delta < 0, 0)
avg_g = gain.ewm(com=period-1, min_periods=period).mean()
avg_l = loss.ewm(com=period-1, min_periods=period).mean()
rs = avg_g / (avg_l + 1e-9)
return 100 - (100 / (1 + rs))

def normalize_factors(df):
“”“因子識別與對齊模組 (安全防吞噬版)”””
if df.empty:
return df
df = df.reset_index(drop=True)
df.columns = [str(c).strip().upper() for c in df.columns]
res = pd.DataFrame()

```
# 日期識別
d_names = ['DATE', 'TIME', '日期', 'INDEX']
d_col = next((c for c in df.columns if any(k in c for k in d_names)), None)
if d_col:
    res['Date_Final'] = pd.to_datetime(df[d_col], errors='coerce')

# 映射配置 (嚴格順序，優先匹配 SP500EW)
m = {
    'SP500EW': ['RSP', 'EW', '等權重', 'SP500EW'],
    'SP500': ['SP500', 'VOO', 'PRICE', '收盤', 'CLOSE'],
    'VIX': ['VIX', '恐慌', '^VIX'],
    'HY_SPREAD': ['SPREAD', 'HY_SPREAD', '利差'],
    'TIPS_10Y': ['TIPS', 'TIPS_10Y', '實質利率'],
    'CAPE': ['CAPE', '席勒', '本益比']
}

used_cols = set()
for target, kws in m.items():
    for col in df.columns:
        if col in used_cols: 
            continue
        if any(k in col for k in kws) and target not in res.columns:
            res[target] = pd.to_numeric(
                df[col].astype(str).str.replace(',', '').str.replace('$', ''), 
                errors='coerce'
            )
            used_cols.add(col)
            break

if 'SP500' in res.columns:
    res['Close'] = res['SP500']

# 補回所有未被使用的原始欄位
for col in df.columns:
    if col not in used_cols and col != d_col:
        res[col] = df[col]

return res.dropna(subset=['Date_Final'])
```

def get_web_data(start_d, end_d):
“”“獲取聯網補丁”””
try:
s = yf.Ticker(“SPY”).history(start=start_d, end=end_d, interval=“1wk”)
v = yf.Ticker(”^VIX”).history(start=start_d, end=end_d, interval=“1wk”)
for d in [s, v]:
if not d.empty:
d.index = d.index.tz_localize(None)
w_df = pd.DataFrame(index=s.index)
w_df[‘SP500_Web’] = s[‘Close’] * 0.9 # VOO 換算比例
w_df[‘VIX_Web’] = v[‘Close’]
w_df.index.name = ‘Date_Final’
return w_df.reset_index()
except Exception as e:
st.warning(f”聯網補強異常: {str(e)}”)
return pd.DataFrame()

# ==========================================

# 3. 側邊欄：資金分配

# ==========================================

st.sidebar.header(“💰 1. 資產分配 (1000萬模型)”)
T_W = st.sidebar.number_input(“總資產 (萬 NTD)”, value=1000)
T_CAP = T_W * 10000

C_W = st.sidebar.number_input(“預備金 (萬 NTD)”, value=200)
C_RSV = C_W * 10000

D_POOL = T_CAP - C_RSV
b_dca_w = st.sidebar.number_input(“月 DCA 基數 (萬 NTD)”, value=20)
B_DCA = b_dca_w * 10000

st.sidebar.header(“🛡️ 2. 熔斷參數”)
M_LOSS = st.sidebar.slider(“虧損熔斷 (%)”, -30, -5, -15) / 100
M_SMA = st.sidebar.number_input(“均線週期 (週)”, value=200)
M_VIX = st.sidebar.slider(“VIX 恐慌門檻”, 20, 60, 40)

st.sidebar.header(“⚙️ 3. 訊號參數”)
R_P = st.sidebar.number_input(“RSI 週期”, value=14)
R_LV1 = st.sidebar.slider(“爆買 RSI (4x)”, 20, 45, 35)
R_LV2 = st.sidebar.slider(“加碼 RSI (2x)”, 30, 55, 45)

up_file = st.sidebar.file_uploader(“📥 4. 上傳 CSV”, type=[‘csv’])

# ==========================================

# 4. 數據對齊模組 (防截斷設計)

# ==========================================

if st.sidebar.button(“🚀 執行強力數據整合”, type=“primary”):
web_df = get_web_data(date(2003, 5, 1), date.today())
if up_file:
df_csv = normalize_factors(pd.read_csv(up_file))
df_csv = df_csv.loc[:, ~df_csv.columns.duplicated()].copy()
df_csv = df_csv.drop_duplicates(subset=[‘Date_Final’])

```
    if not web_df.empty:
        web_df = web_df.drop_duplicates(subset=['Date_Final'])
        final = pd.merge(web_df, df_csv, on='Date_Final', how='outer')
    else:
        final = df_csv
        
    for f in ['SP500', 'VIX']:
        wc = f + "_Web"
        if wc in final.columns:
            if f not in final.columns: 
                final[f] = final[wc]
            else: 
                final[f] = final[f].combine_first(final[wc])
    
    final['Close'] = final['SP500']
    
    # 拆解刪除邏輯，避免長代碼 SyntaxError
    w_cols = [c for c in final.columns if '_Web' in c]
    final = final.drop(columns=w_cols)
    
    # 顯式重命名
    rn_dict = {'Date_Final': 'Date'}
    final = final.rename(columns=rn_dict)
else:
    if web_df.empty: 
        st.stop()
    final = web_df.rename(columns={'Date_Final': 'Date', 'SP500_Web': 'SP500', 'VIX_Web': 'VIX'})
    final['Close'] = final['SP500']

final = final.copy().sort_values('Date').ffill()
st.session_state['master_df'] = final.dropna(subset=['Date', 'Close'])
st.success("✅ 數據載入成功")
```

# ==========================================

# 5. 主面板：監控與回測

# ==========================================

if ‘master_df’ not in st.session_state:
st.info(“💡 請上傳數據後啟動分析”)
st.stop()

df = st.session_state[‘master_df’].copy()
df[‘RSI’] = get_rsi(df[‘Close’], int(R_P))
df[‘SMA’] = df[‘Close’].rolling(window=int(M_SMA), min_periods=1).mean()

# 【重要修正】恢復 52 週滾動最大回撤的精確數學公式

df[‘DD’] = (df[‘Close’] - df[‘Close’].rolling(window=52, min_periods=1).max()) / df[‘Close’].rolling(window=52, min_periods=1).max()

t1, t2 = st.tabs([“📊 即時監控”, “⏳ 歷史回測”])

with t1:
l = df.iloc[-1]
st.subheader(f”基準日: {l[‘Date’].strftime(’%Y-%m-%d’)}”)
c = st.columns(4)
c[0].metric(“VOO 價格”, f”${l[‘Close’]:.2f}”)
c[1].metric(“RSI”, f”{l[‘RSI’]:.1f}”)
c[2].metric(“VIX”, f”{l.get(‘VIX’, 0):.1f}”)
c[3].metric(“回撤 (52週)”, f”{l[‘DD’]:.1%}”)

```
st.markdown("---")
cost = st.number_input("持倉成本", value=450.0)
loss = (l['Close'] - cost) / cost if cost > 0 else 0

# 熔斷判定
is_m = loss < M_LOSS or l['Close'] < l['SMA'] or l.get('VIX', 0) > M_VIX

if is_m: 
    st.error("🔴 熔斷模式啟動 (暫停扣款)")
else:
    if l['RSI'] < R_LV1: 
        st.warning(f"🔥 超賣爆買 ({B_DCA*4/10000:.0f}萬)")
    elif l['RSI'] < R_LV2: 
        st.warning(f"🟡 提速加碼 ({B_DCA*2/10000:.0f}萬)")
    else: 
        st.success(f"🔵 基礎定期定額 ({B_DCA/10000:.0f}萬)")
st.dataframe(df.tail(10))
```

with t2:
st.subheader(“1000 萬資產回測報告”)
sh, d_p, r_p, c_m, hist = 0, D_POOL, C_RSV, -1, []
bh_sh = T_CAP / df[‘Close’].iloc[0]
flags = {‘r15’: False, ‘r25’: False, ‘r35’: False}

```
for i, row in df.iterrows():
    p, dd = row['Close'], row['DD']
    ac = (T_CAP - d_p - r_p) / sh if sh > 0 else 0
    l_bt = (p - ac) / ac if ac > 0 else 0
    
    # 預備金抄底 (15/25/35%)
    for tr, k in [(-0.15, 'r15'), (-0.25, 'r25'), (-0.35, 'r35')]:
        if dd <= tr and not flags[k] and r_p >= C_RSV * 0.3:
            inv = C_RSV * 0.3 if tr > -0.35 else r_p
            sh += inv / p
            r_p -= inv
            flags[k] = True
    if dd >= 0: 
        flags = {key: False for key in flags}
    
    # 每月階梯 DCA
    if row['Date'].month != c_m:
        c_m = row['Date'].month
        melt = l_bt < M_LOSS or p < row['SMA'] or row.get('VIX', 0) > M_VIX
        amt = 0
        if not melt:
            if row['RSI'] < R_LV1: 
                amt = B_DCA * 4
            elif row['RSI'] < R_LV2: 
                amt = B_DCA * 2
            else: 
                amt = B_DCA
        if amt > 0 and d_p >= amt: 
            d_p -= amt
            sh += amt / p
    
    hist.append({
        'Date': row['Date'], 
        'Strategy': sh * p + d_p + r_p, 
        'BH': bh_sh * p
    })

res = pd.DataFrame(hist).set_index('Date')
st.line_chart(res)

# 【重要修正】恢復原始精確的績效計算邏輯 (Pandas 2.3+ 相容)
def mtr(v):
    """計算績效指標"""
    if len(v) < 2:
        return ["N/A", "N/A", "N/A", "N/A"]
    
    # 總報酬率
    tr = (v.iloc[-1] - T_CAP) / T_CAP
    
    # 年化報酬率
    y = len(v) / 52
    cagr = (v.iloc[-1] / T_CAP) ** (1 / y) - 1 if y > 0 else 0
    
    # 最大回撤
    mdd = ((v - v.cummax()) / v.cummax()).min()
    
    # 夏普值 (修正：直接用 pct_change() 不帶參數)
    rets = v.pct_change().dropna()
    sharpe = (cagr - 0.02) / (rets.std() * np.sqrt(52)) if rets.std() > 0 else 0
    
    return [f"{tr:.2%}", f"{cagr:.2%}", f"{mdd:.2%}", f"{sharpe:.2f}"]

st.table(pd.DataFrame({
    "指標": ["總報酬", "年化報酬", "最大回撤", "夏普值"],
    "矛與盾": mtr(res['Strategy']), 
    "B&H": mtr(res['BH'])
}))
```

st.caption(“v9.30 Data Precision Edition | 修復 Pandas 2.3+ & Streamlit 1.55+ 相容性”)
