import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# ==========================================
# 系統與 UI 初始化
# ==========================================
st.set_page_config(page_title="矛與盾 7.16 系統", page_icon="🛡️", layout="wide")
st.title("🛡️ 矛與盾 7.16 整合系統 ⚔️")

# ==========================================
# 工具函數：技術指標
# ==========================================
def calculate_rsi(data, periods=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)
    avg_gain = gain.ewm(com=periods - 1, min_periods=periods).mean()
    avg_loss = loss.ewm(com=periods - 1, min_periods=periods).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def process_market_data(df):
    if df.empty: return df
    df = df.copy()
    df['RSI_14'] = calculate_rsi(df['Close'], periods=14)
    df['200_SMA'] = df['Close'].rolling(window=200, min_periods=1).mean()
    df['52W_High'] = df['Close'].rolling(window=52, min_periods=1).max()
    df['Drawdown'] = (df['Close'] - df['52W_High']) / df['52W_High']
    return df.dropna(subset=['Close', 'RSI_14'])

# ==========================================
# 數據引擎中心 (使用極度穩定的 Ticker API)
# ==========================================
st.sidebar.header("🗄️ 數據引擎中心")
uploaded_file = st.sidebar.file_uploader("上傳歷史 CSV (需含 Close 欄位)", type=['csv'])

if st.sidebar.button("🔄 載入並聯網拼接全量數據庫", type="primary"):
    with st.spinner("正在啟動高穩定數據引擎..."):
        df_csv = pd.DataFrame()
        start_date = "2015-01-01" 
        
        # 1. 處理 CSV
        if uploaded_file is not None:
            try:
                df_csv = pd.read_csv(uploaded_file, index_col=0, parse_dates=True)
                if 'Close' in df_csv.columns:
                    if 'VIX' not in df_csv.columns: df_csv['VIX'] = 20.0 
                    
                    # 強制移除 CSV 時區，避免合併衝突
                    df_csv.index = pd.to_datetime(df_csv.index)
                    if df_csv.index.tz is not None:
                        df_csv.index = df_csv.index.tz_convert(None)
                        
                    last_date = df_csv.index.max()
                    if pd.notnull(last_date):
                        start_date = (last_date - pd.Timedelta(days=7)).strftime('%Y-%m-%d')
            except Exception as e:
                st.sidebar.error(f"CSV 讀取失敗: {e}")
                
        # 2. 使用 Ticker().history() 取代不穩定的 yf.download
        try:
            voo_df = yf.Ticker("VOO").history(start=start_date, interval="1wk")
            vix_df = yf.Ticker("^VIX").history(start=start_date, interval="1wk")
            
            # 強制移除爬蟲數據的時區
            if not voo_df.empty:
                voo_df.index = pd.to_datetime(voo_df.index)
                if voo_df.index.tz is not None:
                    voo_df.index = voo_df.index.tz_convert(None)
            if not vix_df.empty:
                vix_df.index = pd.to_datetime(vix_df.index)
                if vix_df.index.tz is not None:
                    vix_df.index = vix_df.index.tz_convert(None)
            
            # 安全對齊合併
            if not voo_df.empty and not vix_df.empty:
                df_yf = pd.DataFrame({
                    'Close': voo_df['Close'],
                    'VIX': vix_df['Close']
                }).dropna()
            else:
                df_yf = pd.DataFrame()
                
            # 3. 歷史與最新數據拼接
            if not df_csv.empty and not df_yf.empty:
                combined = pd.concat([df_csv[['Close', 'VIX']], df_yf])
                combined = combined[~combined.index.duplicated(keep='last')].sort_index()
            elif not df_csv.empty:
                combined = df_csv
            else:
                combined = df_yf
            
            # 4. 存入系統記憶體
            if combined.empty:
                st.sidebar.error("數據獲取為空，請確認網路狀態。")
            else:
                st.session_state['master_data'] = process_market_data(combined)
                st.sidebar.success(f"✅ 數據就緒！共 {len(st.session_state['master_data'])} 筆。")
        except Exception as e:
            st.sidebar.error(f"網路獲取發生異常: {e}")

# ==========================================
# 介面分頁設定
# ==========================================
tab1, tab2 = st.tabs(["📊 即時監控面板", "⏳ 歷史回測引擎"])

# ------------------------------------------
# 分頁 1：即時監控面板
# ------------------------------------------
with tab1:
    if 'master_data' not in st.session_state:
        st.warning("👈 請先從左側選單載入數據庫")
    else:
        df_live = st.session_state['master_data']
        avg_cost = st.number_input("您的 VOO 平均成本 (USD)", value=450.0)
        latest = df_live.iloc[-1]
        
        cols = st.columns(4)
        cols[0].metric("最新價格", f"${latest['Close']:.2f}")
        cols[1].metric("週線 RSI", f"{latest['RSI_14']:.1f}")
        cols[2].metric("VIX 指數", f"{latest['VIX']:.1f}")
        cols[3].metric("回撤幅度", f"{latest['Drawdown']:.1%}")
        
        p_loss = (latest['Close'] - avg_cost) / avg_cost if avg_cost > 0 else 0
        is_melt = p_loss < -0.15 or (pd.notna(latest['200_SMA']) and latest['Close'] < latest['200_SMA']) or latest['VIX'] > 40
        
        st.divider()
        if is_melt:
            st.error("🔴 熔斷啟動中")
            st.write("執行建議：" + ("允許單次加碼" if latest['RSI_14'] < 30 else "暫停 DCA"))
        else:
            st.success("🟢 系統運行正常")
            if latest['RSI_14'] < 35: st.warning("🔥 模式：超賣加碼 (80萬)")
            elif latest['RSI_14'] < 45: st.warning("🟡 模式：提速扣款 (40萬)")
            else: st.info("🔵 模式：基礎扣款 (20萬)")

# ------------------------------------------
# 分頁 2：歷史回測引擎
# ------------------------------------------
with tab2:
    if 'master_data' in st.session_state:
        st.header("參數化回測")
        with st.expander("⚙️ 調整參數", expanded=False):
            c1, c2 = st.columns(2)
            init_core = c1.number_input("核心資金", value=8000000, step=100000)
            init_rsv = c1.number_input("預備資金", value=1000000, step=100000)
            base_dca = c2.number_input("基礎 DCA", value=200000, step=10000)
            c3, c4, c5 = st.columns(3)
            rsi_weak = c3.number_input("提速閾值", value=45)
            rsi_os = c4.number_input("加碼閾值", value=35)
            rsi_melt = c5.number_input("熔斷閾值", value=30)
            
        if st.button("🚀 開始回測", type="primary"):
            with st.spinner("運算中..."):
                df_bt = st.session_state['master_data']
                core_cash = init_core
                reserve_cash = init_rsv
                shares = avg_cost = 0.0
                rsv_15_used = rsv_25_used = rsv_35_used = False
                history = []
                current_month = -1

                for date, row in df_bt.iterrows():
                    price, rsi, vix_val, sma200, drawdown = row['Close'], row['RSI_14'], row['VIX'], row['200_SMA'], row['Drawdown']
                    portfolio_loss = (price - avg_cost) / avg_cost if avg_cost > 0 else 0
                    
                    if drawdown <= -0.35 and not rsv_35_used and reserve_cash > 0:
                        shares += reserve_cash / price; reserve_cash = 0; rsv_35_used = True
                    elif drawdown <= -0.25 and not rsv_25_used and reserve_cash >= init_rsv*0.3:
                        shares += (init_rsv*0.3) / price; reserve_cash -= (init_rsv*0.3); rsv_25_used = True
                    elif drawdown <= -0.15 and not rsv_15_used and reserve_cash >= init_rsv*0.3:
                        shares += (init_rsv*0.3) / price; reserve_cash -= (init_rsv*0.3); rsv_15_used = True
                        
                    if drawdown >= 0: rsv_15_used = rsv_25_used = rsv_35_used = False

                    if date.month != current_month:
                        current_month = date.month
                        is_meltdown = (portfolio_loss < -0.15) or (pd.notna(sma200) and price < sma200) or (vix_val > 40)
                        dca_amount = 0
                        
                        if is_meltdown:
                            if rsi < rsi_melt: dca_amount = base_dca * 2
                        else:
                            if rsi < rsi_os: dca_amount = base_dca * 4
                            elif rsi < rsi_weak: dca_amount = base_dca * 2
                            else: dca_amount = base_dca
                                
                        if dca_amount > 0 and core_cash >= dca_amount:
                            core_cash -= dca_amount; shares += dca_amount / price
                            
                    total_invested = (init_core - core_cash) + (init_rsv - reserve_cash)
                    avg_cost = total_invested / shares if shares > 0 else 0
                    total_val = (shares * price) + core_cash + reserve_cash
                    history.append({'Date': date, 'Total_Value': total_val, 'Price': price, 'Avg_Cost': avg_cost})
                
                res_df = pd.DataFrame(history)
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
                fig.add_trace(go.Scatter(x=res_df['Date'], y=res_df['Total_Value'], name='總市值'), row=1, col=1)
                fig.add_trace(go.Scatter(x=res_df['Date'], y=res_df['Price'], name='VOO 價格'), row=2, col=1)
                fig.add_trace(go.Scatter(x=res_df['Date'], y=res_df['Avg_Cost'], name='持有均價'), row=2, col=1)
                fig.update_layout(height=600, title_text="回測資產成長曲線")
                
                st.plotly_chart(fig, use_container_width=True)
                st.success(f"回測結束！區間總報酬率：{(res_df.iloc[-1]['Total_Value'] - (init_core + init_rsv)) / (init_core + init_rsv):.2%}")
