import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
import twstock

# --- 1. 頁面基礎設定 ---
st.set_page_config(page_title="全天候戰情室 (Pro)", layout="wide")
st.title("🛡️ 全天候動態曝險系統 (即時零延遲版)")
st.caption("核心：twstock 即時報價 + 雙重備援機制 + 自動 MDD 計算")

# --- 2. 雙重數據抓取引擎 (Hybrid Engine) ---
@st.cache_data(ttl=30) # 縮短快取時間到 30 秒，因為是即時報價
def get_realtime_data():
    # 定義持股清單 (台股代號)
    tw_tickers = ['00675L', '00631L', '00670L', '00662', '00713', '00865B', '00948B']
    
    # 結果儲存容器
    latest_prices = {}
    
    # === A 計畫: 使用 twstock 抓取即時報價 (優先) ===
    try:
        # twstock 支援一次抓多檔 (realtime.get)
        stocks = twstock.realtime.get(tw_tickers)
        
        for code, info in stocks.items():
            if info['success']:
                # 嘗試取得最新成交價 (realtime -> latest_trade_price)
                # 若剛開盤無成交，改拿開盤價或昨日收盤
                price = info['realtime'].get('latest_trade_price', None)
                if not price or price == '-':
                    price = info['realtime'].get('best_bid_price', [None])[0] # 最佳買價
                
                if price and price != '-':
                    latest_prices[code] = float(price)
    except Exception as e:
        st.toast(f"twstock 連線異常，切換備援: {e}", icon="⚠️")

    # === B 計畫: 使用 yfinance 補救 (備援 & 大盤) ===
    # 檢查哪些還沒抓到，以及抓大盤
    missing_tickers = [t for t in tw_tickers if t not in latest_prices]
    yf_tickers = [f"{t}.TW" for t in missing_tickers] + ["^TWII"]
    
    if yf_tickers:
        try:
            yf_data = yf.download(yf_tickers, period="1d", progress=False)['Close']
            
            # 處理大盤
            if "^TWII" in yf_tickers:
                # 兼容不同格式
                try:
                    idx_price = yf_data["^TWII"].iloc[-1] if isinstance(yf_data, pd.DataFrame) else yf_data.iloc[-1]
                    latest_prices["INDEX"] = float(idx_price)
                except:
                    latest_prices["INDEX"] = 0.0

            # 處理補救的個股
            for t in missing_tickers:
                symbol = f"{t}.TW"
                try:
                    price = yf_data[symbol].iloc[-1] if isinstance(yf_data, pd.DataFrame) else yf_data.iloc[-1]
                    latest_prices[t] = float(price)
                except:
                    latest_prices[t] = 0.0 # 真的抓不到就歸零
                    
        except Exception as e:
            st.error(f"yfinance 備援也失敗: {e}")

    # 特別處理：抓取大盤歷史高點 (ATH) - 用 yfinance 抓 5 年
    try:
        hist = yf.Ticker("^TWII").history(period="5y")
        ath = float(hist['High'].max())
    except:
        ath = 32996.0 # 預設值

    return latest_prices, ath

# 執行抓取 (顯示動態狀態)
with st.spinner('正在連線台灣證交所抓取即時報價...'):
    prices, ath_index = get_realtime_data()

# --- 3. 側邊欄：個人持股設定 ---
with st.sidebar:
    st.header("👤 個人持股設定")
    
    # 顯示大盤資訊
    current_index = prices.get("INDEX", 0)
    
    # 計算 MDD
    if ath_index > 0 and current_index > 0:
        mdd_pct = ((ath_index - current_index) / ath_index) * 100
    else:
        mdd_pct = 0.0 # 若抓取失敗
    
    if current_index > 0:
        st.info(f"📊 加權指數: {current_index:,.0f}\n\n📉 目前 MDD: -{mdd_pct:.2f}%")
    else:
        st.error("⚠️ 無法取得大盤指數，請檢查網路")

    with st.form("holdings_form"):
        st.caption("股價來源: 證交所即時 (twstock)")
        
        st.subheader("1. 攻擊型 (股數)")
        s_675 = st.number_input("00675L 持股", value=11000, step=1000)
        s_631 = st.number_input("00631L 持股", value=331, step=100)
        s_670 = st.number_input("00670L 持股", value=616, step=100)
        
        st.subheader("2. 核心型 (股數)")
        s_662 = st.number_input("00662 持股", value=25840, step=100)
        
        st.subheader("3. 防禦型 (股數)")
        s_713 = st.number_input("00713 持股", value=66000, step=1000)
        
        st.subheader("4. 子彈庫 (股數)")
        s_865 = st.number_input("00865B 持股", value=10000, step=1000)
        s_948 = st.number_input("00948B 持股 (若無填0)", value=0, step=1000)
        
        st.subheader("5. 負債設定")
        loan_amount = st.number_input("目前質押借款 (O)", value=2350000, step=10000)
        
        submitted = st.form_submit_button("🔄 更新計算")

# --- 4. 邏輯運算引擎 ---

# A. 階梯策略表
ladder_data = [
    {"MDD區間": "< 5% (高位)", "目標曝險": 23, "位階": "Tier 1"},
    {"MDD區間": "5% ~ 10%", "目標曝險": 23, "位階": "Tier 1 (警戒)"}, 
    {"MDD區間": "10% ~ 25%", "目標曝險": 28, "位階": "Tier 2 (初跌)"},
    {"MDD區間": "25% ~ 40%", "目標曝險": 33, "位階": "Tier 3 (主跌)"},
    {"MDD區間": "40% ~ 50%", "目標曝險": 40, "位階": "Tier 4 (恐慌)"},
    {"MDD區間": "> 50%", "目標曝險": 50, "位階": "Tier 5 (毀滅)"},
]

# B. 判定目前位階
target_attack_ratio = 23.0 
current_tier_index = 0
if mdd_pct < 5.0: target_attack_ratio, current_tier_index = 23.0, 0
elif mdd_pct < 10.0: target_attack_ratio, current_tier_index = 23.0, 1
elif mdd_pct < 25.0: target_attack_ratio, current_tier_index = 28.0, 2
elif mdd_pct < 40.0: target_attack_ratio, current_tier_index = 33.0, 3
elif mdd_pct < 50.0: target_attack_ratio, current_tier_index = 40.0, 4
else: target_attack_ratio, current_tier_index = 50.0, 5

current_tier_name = ladder_data[current_tier_index]["位階"]

# C. 計算資產市值 (使用 prices 字典)
v_675 = prices.get("00675L", 0) * s_675
v_631 = prices.get("00631L", 0) * s_631
v_670 = prices.get("00670L", 0) * s_670
v_662 = prices.get("00662", 0) * s_662
v_713 = prices.get("00713", 0) * s_713
v_865 = prices.get("00865B", 0) * s_865
v_948 = prices.get("00948B", 0) * s_948

val_attack = v_675 + v_631 + v_670
val_core = v_662
val_defense = v_713
val_ammo = v_865 + v_948

total_assets = val_attack + val_core + val_defense + val_ammo
net_assets = total_assets - loan_amount

# D. 計算 Beta
beta_weighted_sum = (
    (v_675 * 1.60) + (v_631 * 1.60) + (v_670 * 2.00) +
    (v_713 * 0.60) + (v_662 * 1.00) +
    (v_865 * 0.00) + (v_948 * -0.10)
)
portfolio_beta = beta_weighted_sum / total_assets if total_assets > 0 else 0

# E. 關鍵比率
maintenance_ratio = (total_assets / loan_amount) * 100 if loan_amount > 0 else 999
loan_ratio = (loan_amount / total_assets) * 100 if total_assets > 0 else 0
current_attack_ratio = (val_attack / total_assets) * 100 if total_assets > 0 else 0

# F. 再平衡計算
gap = current_attack_ratio - target_attack_ratio
threshold = 3.0

# --- 5. 儀表板顯示區 ---

# === 區塊一：戰略位階地圖 ===
st.header("1. 動態戰略地圖")
m1, m2, m3 = st.columns([1, 1, 2])
m1.metric("📉 大盤 MDD", f"-{mdd_pct:.2f}%", f"指數: {current_index:,.0f}")
m2.metric("🎯 目標曝險", f"{target_attack_ratio:.0f}%", f"位階: {current_tier_name}")

df_ladder = pd.DataFrame(ladder_data)
def highlight_current_row(row):
    color = '#ffcccc' if row['位階'] == current_tier_name else ''
    return [f'background-color: {color}' for _ in row]

with m3:
    st.dataframe(df_ladder.style.apply(highlight_current_row, axis=1), hide_index=True, use_container_width=True)

st.divider()

# === 區塊二：核心數據監控 ===
st.header("2. 核心數據監控")
col1, col2, col3, col4 = st.columns(4)

col1.metric("💰 總市值", f"${total_assets:,.0f}", f"淨值: ${net_assets:,.0f}")
col2.metric("📉 Beta", f"{portfolio_beta:.2f}", "目標: 1.05~1.2")

t_color = "normal"
if maintenance_ratio < 250: t_color = "inverse"
elif maintenance_ratio < 300: t_color = "off"
col3.metric("🛡️ 維持率", f"{maintenance_ratio:.0f}%", "安全 > 300%", delta_color=t_color)

l_color = "normal"
if loan_ratio > 35: l_color = "inverse"
col4.metric("💳 負債比", f"{loan_ratio:.1f}%", "安全 < 35%", delta_color=l_color)

st.divider()

# === 區塊三：甜甜圈圖與指令 ===
st.header("3. 配置與指令")
c1, c2 = st.columns([2, 1])

with c1:
    chart_data = pd.DataFrame({
        '資產類別': ['攻擊型 (正二)', '核心 (00662)', '防禦 (00713)', '子彈庫'],
        '市值': [val_attack, val_core, val_defense, val_ammo]
    })
    colors = {'攻擊型 (正二)': '#FF4B4B', '核心 (00662)': '#FFD700', '防禦 (00713)': '#2E8B57', '子彈庫': '#87CEFA'}
    fig = px.pie(chart_data, values='市值', names='資產類別', color='資產類別', color_discrete_map=colors, hole=0.5)
    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
    st.plotly_chart(fig, use_container_width=True)

with c2:
    st.subheader("🤖 AI 戰略指令")
    is_safe_t = maintenance_ratio >= 300
    is_safe_u = loan_ratio <= 35
    
    if maintenance_ratio < 250:
        st.error("⛔ **紅色警戒**\n\n維持率危險！禁止買進，立即還款。")
    elif (not is_safe_t) or (not is_safe_u):
        st.warning("🟠 **風險提示**\n\n財務結構不佳 (T<300% 或 U>35%)。\n禁止大幅加碼。")
        if gap > threshold:
             sell_amt = val_attack - (total_assets * target_attack_ratio / 100)
             st.info(f"💡 **減壓機會**：賣出 ${sell_amt:,.0f} 正二還債！")
    else:
        if gap > threshold:
            sell_amt = val_attack - (total_assets * target_attack_ratio / 100)
            st.warning(f"🔴 **賣出訊號**\n\n攻擊過高 (+{gap:.1f}%)。\n賣出 ${sell_amt:,.0f} 轉入子彈庫。")
        elif gap < -threshold:
            buy_amt = (total_assets * target_attack_ratio / 100) - val_attack
            st.success(f"🟢 **買進訊號**\n\n攻擊過低 ({gap:.1f}%)。\n買進 ${buy_amt:,.0f} 正二。")
        else:
            st.success(f"✅ **系統完美**\n\n無偏離，財務健康。\n持續持有。")

# 自動展開詳細股價 (供查驗)
with st.expander("🔎 查看自動抓取的即時股價 (來源: 證交所/Yahoo)"):
    # 標示資料來源
    source_data = []
    for t in ['00675L', '00631L', '00670L', '00662', '00713', '00865B', '00948B']:
        price = prices.get(t, 0)
        source_data.append({"代號": t, "現價": price})
    
    st.dataframe(pd.DataFrame(source_data))
