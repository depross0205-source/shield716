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
# 共用技術指標函數
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
    df['RSI_14'] = calculate_rsi(df['Close'], periods=14)
    df['200_SMA'] = df['Close'].rolling(window=200).mean()
    df['52W_High'] = df['Close'].rolling(window=52).max()
    df['Drawdown'] = (df['Close'] - df['52W_High']) / df['52W_High']
    return df.dropna()

# ==========================================
# 數據引擎中心 (側邊欄 / 頂部選單)
# ==========================================
st.sidebar.header("🗄️ 數據引擎中心")
st.sidebar.info("💡 邏輯：上傳歷史 CSV，系統將自動比對最後日期，並聯網抓取最新報價進行無縫拼接，確保數據量體最大化。")

uploaded_file = st.sidebar.file_uploader("上傳歷史數據 (可選，需含 Close 欄位)", type=['csv'])

if st.sidebar.button("🔄 載入並聯網拼接全量數據庫", type="primary"):
    with st.spinner("整合歷史與最新數據中..."):
        df_csv = pd.DataFrame()
        start_date = "2015-01-01" # 預設起始日
        
        # 1. 處理手動上傳的歷史數據
        if uploaded_file is not None:
            df_csv = pd.read_csv(uploaded_file, index_col=0, parse_dates=True)
            if 'Close' in df_csv.columns:
                if 'VIX' not in df_csv.columns:
                    df_csv['VIX'] = 20.0 # 若無 VIX 給予預設安全值
                
                # 找出歷史數據最後一天，往前推7天(避免週線切割誤差)作為爬蟲起點
                last_date = df_csv.index.max()
                start_date = (last_date - pd.Timedelta(days=7)).strftime('%Y-%m-%d')
            else:
                st.sidebar.error("CSV 檔案必須包含 'Close' 欄位！")
                
        # 2. 自動爬蟲抓取最新數據
        voo = yf.download("VOO", start=start_date, interval="1wk", progress=False)
        vix = yf.download("^VIX", start=start_date, interval="1wk", progress=False)
        
        if isinstance(voo.columns, pd.MultiIndex):
            voo.columns = voo.columns.droplevel(1)
            vix.columns = vix.columns.droplevel(1)
            
        df_yf = pd.DataFrame({'Close': voo['Close'], 'VIX': vix['Close']}).dropna()
        
        # 3. 數據無縫拼接
        if not df_csv.empty and 'Close' in df_csv.columns:
            # 將 CSV 與 YF 數據上下合併
            combined = pd.concat([df_csv[['Close', 'VIX']], df_yf])
            # 移除重複的日期，保留最新的 (YF) 數據
            combined = combined[~combined.index.duplicated(keep='last')]
            combined = combined.sort_index()
        else:
            combined = df_yf
            
        # 4. 運算所有技術指標並存入記憶體
        st.session_state['master_data'] = process_market_data(combined)
        st.sidebar.success(f"✅ 數據庫就緒！總計包含 {len(st.session_state['master_data'])} 筆週線資料。")

# ==========================================
# 介面分頁設定
# ==========================================
tab1, tab2 = st.tabs(["📊 即時監控面板", "⏳ 歷史回測引擎"])

# ------------------------------------------
# 分頁 1：即時監控面板
# ------------------------------------------
with tab1:
    st.header("VOO 每週狀態監控")
    avg_cost_input = st.number_input("輸入您目前的 VOO 平均成本 (USD)", value=450.0, step=1.0)
    
    if 'master_data' not in st.session_state:
        st.warning("👈 請先從左側選單點擊「載入並聯網拼接全量數據庫」")
    else:
        df_live = st.session_state['master_data']
        latest = df_live.iloc[-1]
        
        price = latest['Close']
        rsi = latest['RSI_14']
        vix_val = latest['VIX']
        drawdown = latest['Drawdown']
        portfolio_loss = (price - avg_cost_input) / avg_cost_input if avg_cost_input > 0 else 0
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("最新收盤價", f"${price:.2f}", f"日期: {latest.name.strftime('%Y-%m-%d')}")
        col2.metric("週線 RSI(14)", f"{rsi:.1f}")
        col3.metric("VIX 恐慌指數", f"{vix_val:.1f}")
        col4.metric("距52週高點回撤", f"{drawdown:.1%}")
        
        st.divider()
        
        # 邏輯判斷
        is_meltdown = portfolio_loss < -0.15 or price < latest['200_SMA'] or vix_val > 40
        
        if is_meltdown:
            st.error("⚠️ 系統狀態：【熔斷機制已觸發】")
            if rsi < 30:
                st.warning(f"🔴 熔斷中：允許單次紀律加碼 (投入 40 萬)")
            else:
                st.error("🔴 熔斷中：暫停所有常規 DCA")
        else:
            st.success("✅ 系統狀態：正常運行中")
            if rsi > 45:
                st.info("🟢 正常/留意區：執行基礎 DCA (投入 20 萬)")
            elif 35 <= rsi <= 45:
                st.warning("🟡 弱勢修正：DCA 提速 (投入 40 萬)")
            elif rsi < 35:
                st.error("🔥 超賣區：提速 + 額外加碼 (投入 80 萬)")
                
        if drawdown <= -0.15:
            st.error(f"🚨 黑天鵝預備金觸發：目前回撤 {drawdown:.1%}，請依紀律動用預備金！")

# ------------------------------------------
# 分頁 2：歷史回測引擎
# ------------------------------------------
with tab2:
    st.header("策略參數設定與回測")
    
    with st.expander("⚙️ 調整資金與 RSI 參數", expanded=False):
        c1, c2 = st.columns(2)
        init_core = c1.number_input("核心初始資金", value=8000000, step=100000)
        init_rsv = c1.number_input("預備金初始資金", value=1000000, step=100000)
        base_dca = c2.number_input("基礎 DCA 金額", value=200000, step=10000)
        
        c3, c4, c5 = st.columns(3)
        rsi_weak = c3.number_input("提速 RSI 閾值", value=45)
        rsi_os = c4.number_input("加碼 RSI 閾值", value=35)
        rsi_melt = c5.number_input("熔斷加碼 RSI 閾值", value=30)
        
    if 'master_data' not in st.session_state:
        st.warning("👈 請先從左側選單點擊「載入並聯網拼接全量數據庫」")
    else:
        df_backtest = st.session_state['master_data']
        
        if st.button("🚀 執行歷史回測", type="primary"):
            with st.spinner("運算回測邏輯中..."):
                core_cash = init_core
                reserve_cash = init_rsv
                shares = 0
                avg_cost = 0.0
                rsv_15_used = rsv_25_used = rsv_35_used = False
                history = []
                current_month = -1

                for date, row in df_backtest.iterrows():
                    price = row['Close']
                    rsi = row['RSI_14']
                    vix_val = row['VIX']
                    sma200 = row['200_SMA']
                    drawdown = row['Drawdown']
                    portfolio_loss = (price - avg_cost) / avg_cost if avg_cost > 0 else 0
                    
                    if drawdown <= -0.35 and not rsv_35_used and reserve_cash > 0:
                        shares += reserve_cash / price
                        reserve_cash = 0
                        rsv_35_used = True
                    elif drawdown <= -0.25 and not rsv_25_used and reserve_cash >= init_rsv*0.3:
                        shares += (init_rsv*0.3) / price
                        reserve_cash -= (init_rsv*0.3)
                        rsv_25_used = True
                    elif drawdown <= -0.15 and not rsv_15_used and reserve_cash >= init_rsv*0.3:
                        shares += (init_rsv*0.3) / price
                        reserve_cash -= (init_rsv*0.3)
                        rsv_15_used = True
                        
                    if drawdown >= 0:
                        rsv_15_used = rsv_25_used = rsv_35_used = False

                    if date.month != current_month:
                        current_month = date.month
                        is_meltdown = (portfolio_loss < -0.15) or (price < sma200) or (vix_val > 40)
                        dca_amount = 0
                        
                        if is_meltdown:
                            if rsi < rsi_melt: dca_amount = base_dca * 2
                        else:
                            if rsi < rsi_os: dca_amount = base_dca * 4
                            elif rsi < rsi_weak: dca_amount = base_dca * 2
                            else: dca_amount = base_dca
                                
                        if dca_amount > 0 and core_cash >= dca_amount:
                            core_cash -= dca_amount
                            shares += dca_amount / price
                            
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
                final_roi = (res_df.iloc[-1]['Total_Value'] - (init_core + init_rsv)) / (init_core + init_rsv)
                st.success(f"回測結束！區間總報酬率：{final_roi:.2%}")
