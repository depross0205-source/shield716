import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, date

st.set_page_config(page_title=chr(83)+chr(104)+chr(105)+chr(101)+chr(108)+chr(100), page_icon=chr(115)+chr(104)+chr(105)+chr(101)+chr(108)+chr(100), layout=chr(119)+chr(105)+chr(100)+chr(101))
st.title(chr(83)+chr(112)+chr(101)+chr(97)+chr(114)+chr(32)+chr(97)+chr(110)+chr(100)+chr(32)+chr(83)+chr(104)+chr(105)+chr(101)+chr(108)+chr(100)+chr(32)+chr(83)+chr(121)+chr(115)+chr(116)+chr(101)+chr(109))

def get_rsi(s, period=14):
delta = s.diff()
gain = delta.where(delta > 0, 0)
loss = -delta.where(delta < 0, 0)
avg_g = gain.ewm(com=period-1, min_periods=period).mean()
avg_l = loss.ewm(com=period-1, min_periods=period).mean()
rs = avg_g / (avg_l + 1e-9)
return 100 - (100 / (1 + rs))

def normalize_factors(df):
if df.empty:
return df
df = df.reset_index(drop=True)
df.columns = [str(c).strip().upper() for c in df.columns]
res = pd.DataFrame()
d_names = [‘DATE’, ‘TIME’, ‘INDEX’]
d_col = next((c for c in df.columns if any(k in c for k in d_names)), None)
if d_col:
res[‘Date_Final’] = pd.to_datetime(df[d_col], errors=‘coerce’)
m = {
‘SP500’: [‘SP500’, ‘VOO’, ‘PRICE’, ‘CLOSE’],
‘VIX’: [‘VIX’],
}
used_cols = set()
for target, kws in m.items():
for col in df.columns:
if col in used_cols: continue
if any(k in col for k in kws) and target not in res.columns:
res[target] = pd.to_numeric(df[col].astype(str).str.replace(’,’, ‘’), errors=‘coerce’)
used_cols.add(col)
break
if ‘SP500’ in res.columns:
res[‘Close’] = res[‘SP500’]
return res.dropna(subset=[‘Date_Final’]) if ‘Date_Final’ in res.columns else res

def get_web_data(start_d, end_d):
try:
s = yf.Ticker(‘SPY’).history(start=start_d, end=end_d, interval=‘1wk’)
v = yf.Ticker(’^VIX’).history(start=start_d, end=end_d, interval=‘1wk’)
for d in [s, v]:
if not d.empty: d.index = d.index.tz_localize(None)
w_df = pd.DataFrame(index=s.index)
w_df[‘SP500_Web’] = s[‘Close’]
w_df[‘VIX_Web’] = v[‘Close’]
w_df.index.name = ‘Date_Final’
return w_df.reset_index()
except Exception as e:
st.warning(str(e))
return pd.DataFrame()

st.sidebar.header(‘Settings’)
T_CAP = 1000000
C_RSV = 200000
D_POOL = T_CAP - C_RSV
B_DCA = 20000
M_LOSS = -0.15
M_SMA = 200
M_VIX = 40
R_P = 14
R_LV1 = 35
R_LV2 = 45

up_file = st.sidebar.file_uploader(‘Upload CSV’, type=[‘csv’])

if st.sidebar.button(‘Run’, type=‘primary’):
web_df = get_web_data(date(2003, 5, 1), date.today())
if up_file:
df_csv = normalize_factors(pd.read_csv(up_file))
df_csv = df_csv.loc[:, ~df_csv.columns.duplicated()].copy()
if not web_df.empty:
web_df = web_df.drop_duplicates(subset=[‘Date_Final’])
final = pd.merge(web_df, df_csv, on=‘Date_Final’, how=‘outer’)
else:
final = df_csv
final[‘Close’] = final[‘SP500’]
final = final.drop(columns=[c for c in final.columns if ‘Web’ in c], errors=‘ignore’)
final = final.rename(columns={‘Date_Final’: ‘Date’})
else:
if web_df.empty: st.stop()
final = web_df.rename(columns={‘Date_Final’: ‘Date’, ‘SP500_Web’: ‘SP500’, ‘VIX_Web’: ‘VIX’})
final[‘Close’] = final[‘SP500’]

```
final = final.sort_values('Date').ffill()
st.session_state['master_df'] = final.dropna(subset=['Date', 'Close'])
st.success('OK')
```

if ‘master_df’ not in st.session_state:
st.info(‘Upload data’)
st.stop()

df = st.session_state[‘master_df’].copy()
df[‘RSI’] = get_rsi(df[‘Close’], R_P)
df[‘SMA’] = df[‘Close’].rolling(window=M_SMA, min_periods=1).mean()

t1, t2 = st.tabs([‘Monitor’, ‘Backtest’])

with t1:
l = df.iloc[-1]
st.metric(‘Price’, f”{l[‘Close’]:.2f}”)
st.dataframe(df.tail(5))

with t2:
sh, d_p, r_p, c_m, hist = 0, D_POOL, C_RSV, -1, []
bh_sh = T_CAP / df[‘Close’].iloc[0]

```
for i, row in df.iterrows():
    p = row['Close']
    if row['Date'].month != c_m:
        c_m = row['Date'].month
        d_p -= B_DCA
        sh += B_DCA / p
    hist.append({'Date': row['Date'], 'Strategy': sh * p + d_p + r_p, 'BH': bh_sh * p})

res = pd.DataFrame(hist).set_index('Date')
st.line_chart(res)
```

st.caption(‘v9.30’)
