import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from fredapi import Fred

st.set_page_config(page_title="矛與盾 v10", layout="wide")
st.title("🛡️ 矛與盾 v10｜雲端版")

# =========================
# 1️⃣ FRED
# =========================
fred = Fred(api_key=st.secrets["FRED_API_KEY"])

@st.cache_data(ttl=86400)
def get_fred():
    hy = fred.get_series("BAMLH0A0HYM2")
    tips = fred.get_series("DFII10")
    cape = fred.get_series("CAPE")

    df = pd.DataFrame({"Date": hy.index, "HY": hy.values})
    df["TIPS"] = tips.reindex(df.index)
    df["CAPE"] = cape.reindex(df.index)

    df["Date"] = pd.to_datetime(df["Date"])
    return df.sort_values("Date").ffill()

# =========================
# 2️⃣ 市場資料
# =========================
@st.cache_data(ttl=3600)
def get_data():
    spy = yf.download("SPY", start="2003-01-01", interval="1wk")
    vix = yf.download("^VIX", start="2003-01-01", interval="1wk")

    if spy.empty or vix.empty:
        st.error("❌ 無法抓取市場資料")
        st.stop()

    spy.index = spy.index.tz_localize(None)
    vix.index = vix.index.tz_localize(None)

    df = pd.DataFrame({
        "Date": spy.index,
        "Close": spy["Close"],
        "VIX": vix["Close"]
    })

    return df.sort_values("Date").ffill().dropna()

# =========================
# 3️⃣ 合併
# =========================
df = get_data()
fred_df = get_fred()

df = pd.merge(df, fred_df, on="Date", how="left")
df = df.sort_values("Date").ffill().dropna()

# 限制資料量（避免雲端卡死）
df = df.tail(1500)

# =========================
# 4️⃣ 指標
# =========================
def get_rsi(s, p=14):
    d = s.diff()
    g = d.clip(lower=0)
    l = -d.clip(upper=0)
    ag = g.ewm(com=p-1).mean()
    al = l.ewm(com=p-1).mean()
    rs = ag / (al + 1e-9)
    return 100 - (100/(1+rs))

df["RSI"] = get_rsi(df["Close"])
df["SMA"] = df["Close"].rolling(200).mean()

# =========================
# 5️⃣ Macro Score
# =========================
def macro(row):
    score = 0
    if row["HY"] > 6: score -= 1
    if row["TIPS"] > 1.5: score -= 1
    if row["CAPE"] > 30: score -= 1
    return score

df["Macro"] = df.apply(macro, axis=1)

# =========================
# 6️⃣ 回測
# =========================
if st.button("🚀 執行回測"):

    cash = 10_000_000
    shares = 0
    history = []
    current_month = None

    for _, r in df.iterrows():
        p = r["Close"]
        date = r["Date"]

        m_key = (date.year, date.month)
        if m_key != current_month:
            current_month = m_key

            invest = 200000

            if r["RSI"] < 30:
                invest *= 4
            elif r["RSI"] < 40:
                invest *= 2

            if r["Macro"] <= -2:
                invest *= 2.5

            if cash >= invest:
                cash -= invest
                shares += invest / p

        total = cash + shares * p

        history.append({"Date": date, "Value": total})

    res = pd.DataFrame(history).set_index("Date")

    st.line_chart(res)
