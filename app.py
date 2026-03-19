import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import date

# Basic Config
st.set_page_config(page_title="Shield", page_icon="shield", layout="wide")
st.title("Spear and Shield v9.60")

def get_rsi(s, period=14):
    delta = s.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_g = gain.ewm(com=period-1, min_periods=period).mean()
    avg_l = loss.ewm(com=period-1, min_periods=period).mean()
    rs = avg_g / (avg_l + 1e-9)
    return 100 - (100 / (1 + rs))

# Core Capital 10M
T_CAP = 10000000
C_RSV = 2000000
D_POOL = T_CAP - C_RSV
B_DCA = 200000

up_file = st.sidebar.file_uploader("Upload CSV", type=["csv"])

if st.sidebar.button("Run System", type="primary"):
    try:
        # Get Web Data Patch
        s = yf.Ticker("SPY").history(start=date(2003, 5, 1), end=date.today(), interval="1wk")
        s.index = s.index.tz_localize(None)
        final = pd.DataFrame({"Date": s.index, "Close": s["Close"].values})
        
        if up_file:
            up_file.seek(0)
            df_csv = pd.read_csv(up_file)
            df_csv.columns = [c.strip().upper() for c in df_csv.columns]
            # Identify Date Column
            d_col = next((c for c in df_csv.columns if "DATE" in c or "日期" in c), None)
            if d_col:
                df_csv["Date"] = pd.to_datetime(df_csv[d_col]).dt.tz_localize(None)
                final = pd.merge(final, df_csv, on="Date", how="outer")
        
        # Data Cleaning
        final = final.sort_values("Date").ffill()
        final = final.dropna(subset=["Close", "Date"])
        st.session_state["master_df"] = final
        st.success("Data alignment complete")
    except Exception as e:
        st.error(f"Error: {str(e)}")

if "master_df" not in st.session_state:
    st.info("Please run data alignment first")
    st.stop()

df = st.session_state["master_df"].copy()
df["RSI"] = get_rsi(df["Close"], 14)

t1, t2 = st.tabs(["Monitor", "Backtest"])

with t1:
    last = df.iloc[-1]
    c = st.columns(3)
    c[0].metric("VOO Price", f"${last['Close']:.2f}")
    c[1].metric("RSI", f"{last['RSI']:.1f}")
    st.dataframe(df.tail(10))

with t2:
    st.subheader("10M Capital Backtest")
    if st.button("Start Backtest"):
        sh, d_rem, r_rem, prev_m, hist = 0, D_POOL, C_RSV, -1, []
        bh_sh = T_CAP / df["Close"].iloc[0]
        
        for _, row in df.iterrows():
            p = row["Close"]
            cur_m = row["Date"].month
            
            # Monthly DCA Logic
            if cur_m != prev_m:
                amt = B_DCA
                if d_rem >= amt:
                    sh += amt / p
                    d_rem -= amt
                prev_m = cur_m
            
            val = (sh * p) + d_rem + r_rem
            bh_val = bh_sh * p
            hist.append({"Date": row["Date"], "Strategy": val, "BH": bh_val})
        
        res_df = pd.DataFrame(hist).set_index("Date")
        st.line_chart(res_df)
        
        # Metrics
        tr = (res_df["Strategy"].iloc[-1] - T_CAP) / T_CAP
        st.metric("Total Return", f"{tr:.2%}")

st.caption("v9.60 Pure ASCII Edition")
