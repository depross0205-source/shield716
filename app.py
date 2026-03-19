import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import traceback
from datetime import date

st.set_page_config(page_title=“mao dun 9.51”, page_icon=“shield”, layout=“wide”)
st.title(“shield mao dun backtest system”)
st.caption(“v9.51 fix FRED column mapping + yfinance protection”)

def get_rsi(s, period=14):
delta = s.diff()
gain  = delta.where(delta > 0, 0)
loss  = -delta.where(delta < 0, 0)
avg_g = gain.ewm(com=period-1, min_periods=period).mean()
avg_l = loss.ewm(com=period-1, min_periods=period).mean()
rs    = avg_g / (avg_l + 1e-9)
return 100 - (100 / (1 + rs))

def normalize_factors(df):
if df.empty:
return df
df = df.reset_index()
df.columns = [str(c).strip().upper() for c in df.columns]
res = pd.DataFrame()

```
d_names = ['DATE', 'TIME', 'INDEX']
d_col   = next((c for c in df.columns if any(k in c for k in d_names)), None)
if d_col:
    res['Date_Final'] = pd.to_datetime(df[d_col], errors='coerce')
    if res['Date_Final'].dt.tz is not None:
        res['Date_Final'] = res['Date_Final'].dt.tz_localize(None)

m = {
    'SP500EW':   ['RSP', 'EW', 'SP500EW'],
    'SP500':     ['SP500', 'VOO', 'PRICE', 'CLOSE'],
    'VIX':       ['VIXCLS', 'VIX'],
    'HY_SPREAD': ['BAMLH0A0HYM2', 'BAML', 'HY_SPREAD', 'SPREAD'],
    'TIPS_10Y':  ['DFII10', 'DFII', 'TIPS_10Y', 'TIPS'],
    'CAPE':      ['CAPE']
}

used_cols = set()
for target, kws in m.items():
    for col in df.columns:
        if col in used_cols:
            continue
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

for col in df.columns:
    if col not in used_cols and col != d_col:
        res[col] = df[col]

if 'Date_Final' in res.columns:
    return res.dropna(subset=['Date_Final'])
return pd.DataFrame()
```

def get_web_data(start_d, end_d):
try:
s = yf.Ticker(“SPY”).history(start=start_d, end=end_d, interval=“1wk”)
v = yf.Ticker(”^VIX”).history(start=start_d, end=end_d, interval=“1wk”)
if s.empty:
raise ValueError(“SPY no data”)
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
st.warning(“yfinance failed: “ + str(e))
return pd.DataFrame()

st.sidebar.header(“1. Capital (10M NTD model)”)
T_W    = st.sidebar.number_input(“Total (wan NTD)”, value=1000)
T_CAP  = T_W * 10000
C_W    = st.sidebar.number_input(“Reserve (wan NTD)”, value=200)
C_RSV  = C_W * 10000
D_POOL = T_CAP - C_RSV
b_dca_w = st.sidebar.number_input(“Monthly DCA base (wan NTD)”, value=20)
B_DCA  = b_dca_w * 10000

st.sidebar.header(“2. Circuit Breaker”)
M_LOSS = st.sidebar.slider(“Loss breaker (%)”, -30, -5, -15) / 100
M_SMA  = st.sidebar.number_input(“SMA period (weeks)”, value=200)
M_VIX  = st.sidebar.slider(“VIX panic threshold”, 20, 60, 40)

st.sidebar.header(“3. Signal params”)
R_P   = st.sidebar.number_input(“RSI period”, value=14)
R_LV1 = st.sidebar.slider(“Oversold RSI 4x”, 20, 45, 35)
R_LV2 = st.sidebar.slider(“Boost RSI 2x”, 30, 55, 45)

st.sidebar.markdown(”—”)
st.sidebar.header(“4. Upload CSV”)
st.sidebar.caption(“FRED columns: SP500, VIXCLS, BAMLH0A0HYM2, DFII10”)
up_file = st.sidebar.file_uploader(“Choose CSV”, type=[‘csv’])

if st.sidebar.button(“Run Data Integration”, type=“primary”):
try:
with st.spinner(“Fetching yfinance data…”):
web_df = get_web_data(date(2003, 5, 1), date.today())

```
    if up_file:
        up_file.seek(0)
        df_csv = normalize_factors(pd.read_csv(up_file))
        if df_csv.empty:
            raise ValueError("CSV empty after normalization. Check date column format YYYY-MM-DD.")

        df_csv = df_csv.loc[:, ~df_csv.columns.duplicated()].copy()
        df_csv = df_csv.drop_duplicates(subset=['Date_Final'])

        mapped_cols = [c for c in ['SP500','VIX','HY_SPREAD','TIPS_10Y','CAPE'] if c in df_csv.columns]
        st.sidebar.success("Mapped: " + str(mapped_cols))

        if not web_df.empty:
            web_df = web_df.drop_duplicates(subset=['Date_Final'])
            final  = pd.merge(web_df, df_csv, on='Date_Final', how='outer')
        else:
            final  = df_csv

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
        final = web_df.rename(columns={
            'Date_Final': 'Date', 'SP500_Web': 'SP500', 'VIX_Web': 'VIX'
        })
        final['Close'] = final['SP500']
    else:
        raise ValueError("No data: yfinance failed and no CSV uploaded.")

    if 'Close' not in final.columns:
        raise ValueError("No price column found. Current columns: " + str(list(final.columns)))

    final = final.sort_values('Date').ffill()
    final = final.dropna(subset=['Date', 'Close'])
    st.session_state['master_df'] = final
    st.success("Loaded " + str(len(final)) + " rows.")

except Exception as e:
    st.error("Integration failed: " + str(e))
    st.code(traceback.format_exc())
```

if ‘master_df’ not in st.session_state:
st.info(“Upload CSV then click Run Data Integration.”)
with st.expander(“CSV column reference”):
st.markdown(”| FRED series | Also accepted | Maps to |\n|—|—|—|\n| SP500 | VOO, PRICE, CLOSE | Close |\n| VIXCLS | VIX | VIX |\n| BAMLH0A0HYM2 | BAML*, HY_SPREAD | HY_SPREAD |\n| DFII10 | DFII*, TIPS | TIPS_10Y |\n| - | CAPE | CAPE |”)
st.stop()

df = st.session_state[‘master_df’].copy()
df[‘RSI’] = get_rsi(df[‘Close’], R_P)
df[‘SMA’] = df[‘Close’].rolling(window=M_SMA, min_periods=1).mean()
df[‘DD’]  = (
(df[‘Close’] - df[‘Close’].rolling(52, min_periods=1).max())
/ df[‘Close’].rolling(52, min_periods=1).max()
)

t1, t2 = st.tabs([“Monitor”, “Backtest”])

with t1:
l = df.iloc[-1]
st.subheader(“Latest: “ + str(pd.Timestamp(l[‘Date’]).strftime(’%Y-%m-%d’)))
c = st.columns(4)
c[0].metric(“Price”,     “$” + f”{l[‘Close’]:.2f}”)
c[1].metric(“RSI”,       f”{l[‘RSI’]:.1f}”)
vix_val = float(l[‘VIX’]) if ‘VIX’ in l.index and not pd.isna(l.get(‘VIX’, float(‘nan’))) else 0.0
c[2].metric(“VIX”,       f”{vix_val:.1f}”)
c[3].metric(“DD 52w”,    f”{l[‘DD’]:.1%}”)

```
st.markdown("---")
cost = st.number_input("Cost basis ($)", value=450.0)
loss = (l['Close'] - cost) / cost if cost > 0 else 0
is_m = loss < M_LOSS or l['Close'] < l['SMA'] or vix_val > M_VIX

if is_m:
    st.error("CIRCUIT BREAKER ACTIVE")
else:
    if   l['RSI'] < R_LV1: st.warning("OVERSOLD 4x DCA: " + str(B_DCA*4//10000) + " wan")
    elif l['RSI'] < R_LV2: st.warning("BOOST 2x DCA: " + str(B_DCA*2//10000) + " wan")
    else:                   st.success("Normal DCA: " + str(B_DCA//10000) + " wan")

with st.expander("Loaded columns"):
    st.write(list(df.columns))
st.dataframe(df.tail(10))
```

with t2:
st.subheader(“10M Capital Backtest”)

```
if st.button("Run Backtest", key="run_backtest"):
    try:
        with st.spinner("Computing..."):
            sh, d_p, r_p, c_m, hist = 0, D_POOL, C_RSV, -1, []
            first_price = df['Close'].iloc[0]
            bh_sh = T_CAP / first_price if first_price > 0 else 0
            flags = {'r15': False, 'r25': False, 'r35': False}

            for _, row in df.iterrows():
                p  = row['Close']
                dd = row['DD']
                if not np.isfinite(p) or p <= 0:
                    continue

                ac   = (T_CAP - d_p - r_p) / sh if sh > 0 else 0
                l_bt = (p - ac) / ac              if ac > 0 else 0

                for tr, k in [(-0.15,'r15'), (-0.25,'r25'), (-0.35,'r35')]:
                    if dd <= tr and not flags[k] and r_p >= C_RSV * 0.3:
                        inv = C_RSV * 0.3 if tr > -0.35 else r_p
                        sh += inv / p
                        r_p -= inv
                        flags[k] = True
                if dd >= -0.001:
                    flags = {k: False for k in flags}

                row_date = pd.Timestamp(row['Date'])
                if row_date.month != c_m:
                    c_m   = row_date.month
                    v_val = float(row.get('VIX', 0) or 0)
                    if not np.isfinite(v_val):
                        v_val = 0.0
                    melt = l_bt < M_LOSS or p < row['SMA'] or v_val > M_VIX
                    amt  = 0
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
            st.error("No backtest data. Check Close column.")
            st.stop()

        res = pd.DataFrame(hist).set_index('Date')
        st.line_chart(res)

        def mtr(v):
            if v.empty or v.iloc[0] <= 0:
                return ['N/A','N/A','N/A','N/A']
            tr   = (v.iloc[-1] - T_CAP) / T_CAP
            y    = max(len(v) / 52.0, 1.0)
            cagr = (v.iloc[-1] / T_CAP) ** (1/y) - 1
            cum  = v.cummax().replace(0, np.nan)
            mdd  = ((v - cum) / cum).min()
            rets = v.pct_change(fill_method=None).dropna()
            shrp = ((cagr - 0.02) / (rets.std() * np.sqrt(52))
                    if not rets.empty and rets.std() > 0 else 0)
            return [f"{tr:.2%}", f"{cagr:.2%}", f"{mdd:.2%}", f"{shrp:.2f}"]

        st.table(pd.DataFrame({
            'Metric':   ['Total Return','CAGR','Max Drawdown','Sharpe'],
            'Strategy': mtr(res['Strategy']),
            'BH':       mtr(res['BH'])
        }))

    except Exception as e:
        st.error("Backtest error: " + str(e))
        st.code(traceback.format_exc())
```

st.caption(“v9.51 | fix FRED VIXCLS/BAMLH0A0HYM2/DFII10 mapping + yfinance guard”)
