import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, date

st.set_page_config(page_title=“Shield”, page_icon=“shield”, layout=“wide”)
st.title(“Spear and Shield”)

def get_rsi(s, period=14):
delta = s.diff()
gain = delta.where(delta > 0, 0)
loss = -delta.where(delta < 0, 0)
avg_g = gain.ewm(com=period-1, min_periods=period).mean()
avg_l = loss.ewm(com=period-1, min_periods=period).mean()
rs = avg_g / (avg_l + 1e-9)
return 100 - (100 / (1 + rs))

st.sidebar.header(“Settings”)
T_CAP = 1000000
C_RSV = 200000
D_POOL = T_CAP - C_RSV
B_DCA = 20000

up_file = st.sidebar.file_uploader(“Upload CSV”, type=[“csv”])

if st.sidebar.button(“Run”, type=“primary”):
try:
s = yf.Ticker(“SPY”).history(start=date(2003, 5, 1), end=date.today(), interval=“1wk”)
s.index = s.index.tz_localize(None)
if up_file:
df_csv = pd.read_csv(up_file)
df_csv.columns = [str(c).strip().upper() for c in df_csv.columns]
for c in df_csv.columns:
if “DATE” in c:
df_csv[“Date”] = pd.to_datetime(df_csv[c])
break
df_csv = df_csv[df_csv[“Date”].notna()].copy()
final = pd.merge(pd.DataFrame({“Date”: s.index, “Close”: s[“Close”].values}), df_csv, on=“Date”, how=“outer”)
else:
final = pd.DataFrame({“Date”: s.index, “Close”: s[“Close”].values})

```
    final = final.sort_values("Date").dropna(subset=["Close"])
    st.session_state["master_df"] = final
    st.success("OK")
except Exception as e:
    st.error(str(e))
```

if “master_df” not in st.session_state:
st.info(“Upload data”)
st.stop()

df = st.session_state[“master_df”].copy()
df[“RSI”] = get_rsi(df[“Close”], 14)

t1, t2 = st.tabs([“Monitor”, “Backtest”])

with t1:
l = df.iloc[-1]
st.metric(“Price”, f”{l[‘Close’]:.2f}”)
st.dataframe(df.tail(5))

with t2:
sh = 0
d_p = D_POOL
hist = []
bh_sh = T_CAP / df[“Close”].iloc[0]
c_m = -1

```
for i, row in df.iterrows():
    p = row["Close"]
    if row["Date"].month != c_m:
        c_m = row["Date"].month
        d_p = d_p - B_DCA
        sh = sh + (B_DCA / p)
    hist.append({"Date": row["Date"], "Strategy": sh * p + d_p, "BH": bh_sh * p})

res = pd.DataFrame(hist).set_index("Date")
st.line_chart(res)
```

st.caption(“v9.30”)
