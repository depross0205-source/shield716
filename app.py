import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import traceback
from datetime import datetime, date

# ==========================================

# 1. 系統基礎配置

# ==========================================

st.set_page_config(page_title=“矛與盾 9.51”, page_icon=“🛡️”, layout=“wide”)
st.title(“🛡️ 矛與盾 數據精確與穩定回測系統 ⚔️”)
st.caption(“v9.51 — 修正 FRED 欄位映射失敗 & yfinance 熔斷保護”)

# ==========================================

# 2. 核心運算函數

# ==========================================

def get_rsi(s, period=14):
delta = s.diff()
gain  = delta.where(delta > 0, 0)
loss  = -delta.where(delta < 0, 0)
avg_g = gain.ewm(com=period-1, min_periods=period).mean()
avg_l = loss.ewm(com=period-1, min_periods=period).mean()
rs    = avg_g / (avg_l + 1e-9)
return 100 - (100 / (1 + rs))

def normalize_factors(df):
“””
因子對齊模組 v2
─────────────────────────────────────────
修正清單：
· VIXCLS      → VIX        (FRED 系列名)
· BAMLH0A0HYM2 / BAML* → HY_SPREAD
· DFII10 / DFII*        → TIPS_10Y
“””
if df.empty: return df
df = df.reset_index()
df.columns = [str(c).strip().upper() for c in df.columns]
res = pd.DataFrame()

```
# ── 日期欄識別與時區剝離 ──────────────────
d_names = ['DATE', 'TIME', '日期', 'INDEX']
d_col   = next((c for c in df.columns if any(k in c for k in d_names)), None)
if d_col:
    res['Date_Final'] = pd.to_datetime(df[d_col], errors='coerce')
    if res['Date_Final'].dt.tz is not None:
        res['Date_Final'] = res['Date_Final'].dt.tz_localize(None)

# ── 欄位映射表（新增 FRED 原始系列名）────────
m = {
    'SP500EW':   ['RSP', 'EW', '等權重', 'SP500EW'],
    'SP500':     ['SP500', 'VOO', 'PRICE', '收盤', 'CLOSE'],
    'VIX':       ['VIX', 'VIXCLS', '恐慌', '^VIX'],            # ✅ +VIXCLS
    'HY_SPREAD': ['SPREAD', 'HY_SPREAD', '利差',
                  'BAML', 'BAMLH0A0HYM2'],                      # ✅ +BAML 系列
    'TIPS_10Y':  ['TIPS', 'TIPS_10Y', '實質利率',
                  'DFII10', 'DFII'],                            # ✅ +DFII 系列
    'CAPE':      ['CAPE', '席勒', '本益比']
}

used_cols = set()
for target, kws in m.items():
    for col in df.columns:
        if col in used_cols: continue
        if any(k.upper() in col for k in kws) and target not in res.columns:
            res[target] = pd.to_numeric(
                df[col].astype(str)
                       .str.replace(',', '', regex=False)
                       .str.replace('$', '', regex=False),
                errors='coerce'
            )
            used_cols.add(col)
            break

if 'SP500' in res.columns:
    res['Close'] = res['SP500']

# 補回未使用的原始欄位
for col in df.columns:
    if col not in used_cols and col != d_col:
        res[col] = df[col]

return res.dropna(subset=['Date_Final']) if 'Date_Final' in res.columns else pd.DataFrame()
```

def get_web_data(start_d, end_d):
“””
yfinance 補強 — 失敗不崩潰，回傳空 DataFrame 即可
“””
try:
s = yf.Ticker(“SPY”).history(start=start_d, end=end_d, interval=“1wk”)
v = yf.Ticker(”^VIX”).history(start=start_d, end=end_d, interval=“1wk”)
if s.empty:
raise ValueError(“SPY 無資料”)
for d in [s, v]:
if not d.empty and d.index.tz is not None:
d.index = d.index.tz_localize(None)
w_df = pd.DataFrame(index=s.index)
w_df[‘SP500_Web’] = s[‘Close’] * 0.9
if not v.empty:
w_df[‘VIX_Web’] = v[‘Close’].reindex(s.index).ffill()
w_df.index.name = ‘Date_Final’
return w_df.reset_index()
except Exception as e:
st.warning(f”⚠️ yfinance 聯網補強失敗（已略過）: {e}”)
return pd.DataFrame()   # ✅ 不再崩潰，改為回傳空值

# ==========================================

# 3. 側邊欄

# ==========================================

st.sidebar.header(“💰 1. 資產分配 (1000萬模型)”)
T_W    = st.sidebar.number_input(“總資產 (萬 NTD)”, value=1000)
T_CAP  = T_W * 10000
C_W    = st.sidebar.number_input(“預備金 (萬 NTD)”, value=200)
C_RSV  = C_W * 10000
D_POOL = T_CAP - C_RSV
b_dca_w = st.sidebar.number_input(“月 DCA 基數 (萬 NTD)”, value=20)
B_DCA  = b_dca_w * 10000

st.sidebar.header(“🛡️ 2. 熔斷參數”)
M_LOSS = st.sidebar.slider(“虧損熔斷 (%)”, -30, -5, -15) / 100
M_SMA  = st.sidebar.number_input(“均線週期 (週)”, value=200)
M_VIX  = st.sidebar.slider(“VIX 恐慌門檻”, 20, 60, 40)

st.sidebar.header(“⚙️ 3. 訊號參數”)
R_P    = st.sidebar.number_input(“RSI 週期”, value=14)
R_LV1  = st.sidebar.slider(“爆買 RSI (4x)”, 20, 45, 35)
R_LV2  = st.sidebar.slider(“加碼 RSI (2x)”, 30, 55, 45)

st.sidebar.markdown(”—”)
st.sidebar.header(“📥 4. 上傳 CSV”)
st.sidebar.caption(
“支援 FRED 欄位名：SP500, VIXCLS, BAMLH0A0HYM2, DFII10\n”
“或中文欄位：收盤, 恐慌指數, 利差, 實質利率”
)
up_file = st.sidebar.file_uploader(“選擇 CSV 檔案”, type=[‘csv’])

# ==========================================

# 4. 數據整合

# ==========================================

if st.sidebar.button(“🚀 執行強力數據整合”, type=“primary”):
try:
# Step 1：嘗試聯網（失敗也沒關係）
with st.spinner(“嘗試 yfinance 聯網補強…”):
web_df = get_web_data(date(2003, 5, 1), date.today())

```
    # Step 2：讀取 CSV
    if up_file:
        up_file.seek(0)
        df_csv = normalize_factors(pd.read_csv(up_file))
        if df_csv.empty:
            raise ValueError("CSV 對齊後為空，請確認日期欄位格式（建議 YYYY-MM-DD）。")

        df_csv = df_csv.loc[:, ~df_csv.columns.duplicated()].copy()
        df_csv = df_csv.drop_duplicates(subset=['Date_Final'])

        # 映射診斷（側邊欄顯示）
        mapped_cols = [c for c in ['SP500','VIX','HY_SPREAD','TIPS_10Y','CAPE']
                       if c in df_csv.columns]
        st.sidebar.success(f"CSV 已映射欄位：{mapped_cols}")

        if not web_df.empty:
            web_df  = web_df.drop_duplicates(subset=['Date_Final'])
            final   = pd.merge(web_df, df_csv, on='Date_Final', how='outer')
        else:
            final   = df_csv

        for f in ['SP500', 'VIX']:
            wc = f + "_Web"
            if wc in final.columns:
                if f not in final.columns:
                    final[f] = final[wc]
                else:
                    final[f] = final[f].combine_first(final[wc])

        final['Close'] = final['SP500']
        w_cols = [c for c in final.columns if '_Web' in c]
        final  = final.drop(columns=w_cols)
        final  = final.rename(columns={'Date_Final': 'Date'})

    elif not web_df.empty:
        # 純聯網模式
        final = web_df.rename(columns={
            'Date_Final': 'Date', 'SP500_Web': 'SP500', 'VIX_Web': 'VIX'
        })
        final['Close'] = final['SP500']
    else:
        raise ValueError(
            "❌ 無法取得資料：yfinance 失敗且未上傳 CSV。\n"
            "請從 FRED 下載 SP500 / VIXCLS 的 CSV 後上傳。"
        )

    if 'Close' not in final.columns:
        raise ValueError(
            "找不到價格欄位（Close / SP500 / 收盤）。\n"
            f"目前欄位：{list(final.columns)}"
        )

    final = final.sort_values('Date').ffill()
    final = final.dropna(subset=['Date', 'Close'])
    st.session_state['master_df'] = final
    st.success(f"✅ 數據載入成功！共 {len(final)} 筆，請切換至右側分析頁。")

except Exception as e:
    st.error(f"❌ 整合失敗: {str(e)}")
    st.code(traceback.format_exc())
```

# ==========================================

# 5. 主面板

# ==========================================

if ‘master_df’ not in st.session_state:
st.info(“💡 請上傳 CSV（或直接網路模式），點擊左側「🚀 執行強力數據整合」啟動分析。”)
with st.expander(“📋 CSV 欄位對照表”):
st.markdown(”””

|FRED 系列     |亦可接受                 |映射為          |
|------------|---------------------|-------------|
|SP500       |VOO, PRICE, CLOSE, 收盤|Close / SP500|
|VIXCLS      |VIX, ^VIX, 恐慌        |VIX          |
|BAMLH0A0HYM2|SPREAD, HY_SPREAD, 利差|HY_SPREAD    |
|DFII10      |TIPS, TIPS_10Y, 實質利率 |TIPS_10Y     |
|—           |CAPE, 席勒, 本益比        |CAPE         |
|“””)        |                     |             |

```
st.stop()
```

df = st.session_state[‘master_df’].copy()
df[‘RSI’] = get_rsi(df[‘Close’], R_P)
df[‘SMA’] = df[‘Close’].rolling(window=M_SMA, min_periods=1).mean()
df[‘DD’]  = (
(df[‘Close’] - df[‘Close’].rolling(52, min_periods=1).max())
/ df[‘Close’].rolling(52, min_periods=1).max()
)

t1, t2 = st.tabs([“📊 即時監控”, “⏳ 歷史回測”])

# ─── Tab 1：即時監控 ─────────────────────────────────

with t1:
l = df.iloc[-1]
st.subheader(f”基準日: {pd.Timestamp(l[‘Date’]).strftime(’%Y-%m-%d’)}”)
c = st.columns(4)
c[0].metric(“VOO 價格”,     f”${l[‘Close’]:.2f}”)
c[1].metric(“RSI”,          f”{l[‘RSI’]:.1f}”)
vix_val = float(l[‘VIX’]) if ‘VIX’ in l and not pd.isna(l[‘VIX’]) else 0.0
c[2].metric(“VIX”,          f”{vix_val:.1f}”)
c[3].metric(“回撤 (52週)”, f”{l[‘DD’]:.1%}”)

```
st.markdown("---")
cost  = st.number_input("持倉成本 ($)", value=450.0)
loss  = (l['Close'] - cost) / cost if cost > 0 else 0
is_m  = loss < M_LOSS or l['Close'] < l['SMA'] or vix_val > M_VIX

if is_m:
    st.error("🔴 熔斷模式啟動（暫停扣款）")
else:
    if   l['RSI'] < R_LV1: st.warning(f"🔥 超賣爆買 ({B_DCA*4/10000:.0f} 萬)")
    elif l['RSI'] < R_LV2: st.warning(f"🟡 提速加碼 ({B_DCA*2/10000:.0f} 萬)")
    else:                   st.success( f"🔵 基礎定期定額 ({B_DCA/10000:.0f} 萬)")

# 現有欄位一覽
with st.expander("🔎 已載入欄位"):
    st.write(list(df.columns))
st.dataframe(df.tail(10))
```

# ─── Tab 2：歷史回測 ─────────────────────────────────

with t2:
st.subheader(“1000 萬資產回測報告”)

```
if st.button("▶️ 開始執行策略回測", key="run_backtest"):
    try:
        with st.spinner("正在運算 1000 萬資產配置邏輯..."):
            sh, d_p, r_p, c_m, hist = 0, D_POOL, C_RSV, -1, []
            first_price = df['Close'].iloc[0]
            bh_sh = T_CAP / first_price if first_price > 0 else 0
            flags = {'r15': False, 'r25': False, 'r35': False}

            for _, row in df.iterrows():
                p  = row['Close']
                dd = row['DD']
                if not np.isfinite(p) or p <= 0: continue

                ac   = (T_CAP - d_p - r_p) / sh if sh > 0 else 0
                l_bt = (p - ac) / ac              if ac > 0 else 0

                # 預備金抄底 15/25/35%
                for tr, k in [(-0.15,'r15'), (-0.25,'r25'), (-0.35,'r35')]:
                    if dd <= tr and not flags[k] and r_p >= C_RSV * 0.3:
                        inv = C_RSV * 0.3 if tr > -0.35 else r_p
                        sh += inv / p
                        r_p -= inv
                        flags[k] = True
                if dd >= -0.001:   # 接近新高時重置
                    flags = {k: False for k in flags}

                # 每月 DCA
                row_date = pd.Timestamp(row['Date'])
                if row_date.month != c_m:
                    c_m   = row_date.month
                    v_val = float(row['VIX']) if 'VIX' in row.index and not pd.isna(row.get('VIX')) else 0.0
                    melt  = l_bt < M_LOSS or p < row['SMA'] or v_val > M_VIX
                    amt   = 0
                    if not melt:
                        if   row['RSI'] < R_LV1: amt = B_DCA * 4
                        elif row['RSI'] < R_LV2: amt = B_DCA * 2
                        else:                     amt = B_DCA
                    if amt > 0 and d_p >= amt:
                        d_p -= amt
                        sh  += amt / p

                hist.append({
                    'Date':     row_date,
                    'Strategy': sh * p + d_p + r_p,
                    'BH':       bh_sh * p
                })

        if not hist:
            st.error("回測無資料產生，請確認 Close 欄位是否存在。")
            st.stop()

        res = pd.DataFrame(hist).set_index('Date')
        st.line_chart(res)

        def mtr(v, label=""):
            if v.empty or v.iloc[0] <= 0:
                return ["N/A"] * 4
            init = T_CAP
            tr   = (v.iloc[-1] - init) / init
            y    = max(len(v) / 52.0, 1.0)
            cagr = (v.iloc[-1] / init) ** (1/y) - 1
            cum  = v.cummax()
            mdd  = ((v - cum) / cum.replace(0, np.nan)).min()
            rets = v.pct_change(fill_method=None).dropna()
            shrp = (
                (cagr - 0.02) / (rets.std() * np.sqrt(52))
                if not rets.empty and rets.std() > 0 else 0
            )
            return [f"{tr:.2%}", f"{cagr:.2%}", f"{mdd:.2%}", f"{shrp:.2f}"]

        kpi = pd.DataFrame({
            "指標":    ["總報酬", "年化報酬", "最大回撤", "夏普值"],
            "矛與盾": mtr(res['Strategy']),
            "B&H":    mtr(res['BH'])
        })
        st.table(kpi)

    except Exception as e:
        st.error(f"❌ 回測運算錯誤: {str(e)}")
        st.code(traceback.format_exc())
```

st.caption(“v9.51 | 修正：FRED VIXCLS / BAMLH0A0HYM2 / DFII10 欄位映射 + yfinance 失敗保護”)
