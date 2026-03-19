import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

# ==========================================
# 1. 參數設定區
# ==========================================
CORE_CAPITAL = 8000000
BASE_DCA = 200000
RESERVE_CAPITAL = 1000000
CURRENT_AVG_COST = 450.0  # 請在此修改為您實際的 VOO 平均成本

# ==========================================
# 2. 技術指標計算
# ==========================================
def calculate_rsi(data, periods=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)
    avg_gain = gain.ewm(com=periods - 1, min_periods=periods).mean()
    avg_loss = loss.ewm(com=periods - 1, min_periods=periods).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def fetch_and_prepare_data():
    voo = yf.download("VOO", period="5y", interval="1wk", progress=False)
    vix = yf.download("^VIX", period="5y", interval="1wk", progress=False)
    
    if isinstance(voo.columns, pd.MultiIndex):
        voo.columns = voo.columns.droplevel(1)
        vix.columns = vix.columns.droplevel(1)
        
    df = pd.DataFrame()
    df['Close'] = voo['Close']
    df['Volume'] = voo['Volume']
    df['VIX'] = vix['Close']
    df = df.dropna()
    
    df['RSI_14'] = calculate_rsi(df['Close'], periods=14)
    df['200_SMA'] = df['Close'].rolling(window=200).mean()
    df['52W_High'] = df['Close'].rolling(window=52).max()
    df['Drawdown'] = (df['Close'] - df['52W_High']) / df['52W_High']
    return df

# ==========================================
# 3. 核心決策與 HTML 網頁產出
# ==========================================
def generate_html(df, avg_cost):
    latest = df.iloc[-1]
    
    current_price = latest['Close']
    current_rsi = latest['RSI_14']
    current_vix = latest['VIX']
    sma_200 = latest['200_SMA']
    drawdown = latest['Drawdown']
    
    portfolio_loss = (current_price - avg_cost) / avg_cost if avg_cost > 0 else 0
    
    # 判斷熔斷
    is_meltdown = False
    meltdown_text = ""
    if portfolio_loss < -0.15 or current_price < sma_200 or current_vix > 40:
        is_meltdown = True
        meltdown_text = "⚠️ 熔斷機制已觸發"
        
    # 判斷 DCA
    action = ""
    dca_amount = 0
    action_color = "#4caf50" # 預設綠色
    
    if is_meltdown:
        action_color = "#ff4d4d" # 紅色
        if current_rsi < 30:
            action = "🔴 熔斷中：允許單次紀律加碼 (RSI < 30)"
            dca_amount = BASE_DCA * 2
        else:
            action = "🔴 熔斷中：暫停常規 DCA"
            dca_amount = 0
    else:
        if current_rsi > 45:
            action = "🟢 正常/留意區：執行基礎 DCA"
            dca_amount = BASE_DCA
        elif 35 <= current_rsi <= 45:
            action = "🟡 弱勢修正：DCA 提速"
            dca_amount = BASE_DCA * 2
            action_color = "#ffd700"
        elif current_rsi < 35:
            action = "🔥 超賣區：提速 + 額外加碼"
            dca_amount = BASE_DCA * 4
            action_color = "#ff9800"
            
    # 判斷預備金
    reserve_action = "無須動用預備金"
    reserve_color = "#ffffff"
    if drawdown <= -0.35:
        reserve_action = "🚨 嚴重崩盤 (-35%)：動用剩餘 40 萬預備金 All in！"
        reserve_color = "#ff4d4d"
    elif drawdown <= -0.25:
        reserve_action = "🚨 深度回撤 (-25%)：動用 30 萬預備金買入！"
        reserve_color = "#ff9800"
    elif drawdown <= -0.15:
        reserve_action = "🚨 達標回撤 (-15%)：動用 30 萬預備金買入！"
        reserve_color = "#ffd700"

    # 生成手機版 UI 的 HTML
    html_content = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>矛與盾 7.16 儀表板</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #121212; color: #ffffff; padding: 15px; margin: 0; }}
            .container {{ max-width: 600px; margin: 0 auto; }}
            .card {{ background-color: #1e1e1e; border-radius: 12px; padding: 20px; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.5); }}
            h1 {{ color: #e0e0e0; font-size: 22px; text-align: center; border-bottom: 1px solid #333; padding-bottom: 15px; }}
            h2 {{ color: #aaaaaa; font-size: 16px; margin-top: 0; }}
            .data-row {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #2a2a2a; font-size: 15px; }}
            .data-row:last-child {{ border-bottom: none; }}
            .value {{ font-weight: bold; }}
            .action-text {{ font-size: 18px; font-weight: bold; margin: 15px 0 5px 0; color: {action_color}; }}
            .amount {{ font-size: 24px; font-weight: bold; color: #4db8ff; }}
            .reserve {{ color: {reserve_color}; font-weight: bold; }}
            .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🛡️ 矛與盾 7.16 儀表板 ⚔️</h1>
            
            <div class="card">
                <h2>📊 VOO 數據監控</h2>
                <div class="data-row"><span>最新收盤價</span> <span class="value">${current_price:.2f}</span></div>
                <div class="data-row"><span>週線 RSI(14)</span> <span class="value">{current_rsi:.2f}</span></div>
                <div class="data-row"><span>VIX 恐慌指數</span> <span class="value">{current_vix:.2f}</span></div>
                <div class="data-row"><span>距52週高點回撤</span> <span class="value">{drawdown:.2%}</span></div>
                <div class="data-row"><span>系統狀態</span> <span class="value">{ "✅ 正常運行" if not is_meltdown else meltdown_text }</span></div>
            </div>

            <div class="card">
                <h2>🎯 核心 DCA 執行指令</h2>
                <div class="action-text">{action}</div>
                <div class="data-row"><span>建議投入金額</span> <span class="amount">{dca_amount:,} <span style="font-size:14px;color:#888;">TWD</span></span></div>
            </div>

            <div class="card">
                <h2>🏦 100萬黑天鵝預備金</h2>
                <div class="reserve" style="padding-top:10px;">{reserve_action}</div>
            </div>
            
            <div class="footer">
                數據更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (UTC)
            </div>
        </div>
    </body>
    </html>
    """
    
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html_content)

if __name__ == "__main__":
    historical_data = fetch_and_prepare_data()
    generate_html(historical_data, CURRENT_AVG_COST)
