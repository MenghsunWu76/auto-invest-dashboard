import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from datetime import datetime, timedelta
import pytz

# --- 1. 頁面設定 ---
st.set_page_config(page_title="全天候戰情室 (Stable)", layout="wide")
st.title("🛡️ 全天候動態曝險系統 (抗崩潰版)")
st.caption("核心：Yahoo Finance 數據 + 手動修正模式 + 雙重風控")

# --- 2. 數據抓取引擎 (更強健的 Yahoo 抓取) ---
@st.cache_data(ttl=60)
def get_market_data():
    tickers = {
        "00675L": "00675L.TW",
        "00631L": "00631L.TW",
        "00670L": "00670L.TW",
        "00662": "00662.TW",
        "00713": "00713.TW",
        "00865B": "00865B.TW",
        "00948B": "00948B.TW",
        "INDEX": "^TWII"
    }
    
    latest_prices = {}
    
    # 技巧：抓取過去 5 天的數據，而不是 1 天
    # 這樣可以避免因為時區問題 (UTC vs TW) 導致抓到空資料
    try:
        data = yf.download(list(tickers.values()), period="5d", progress=False)['Close']
        
        for key, symbol in tickers.items():
            try:
                # 取得該檔股票最後一筆「非 NaN」的價格
                if isinstance(data, pd.DataFrame):
                    # 處理多層索引或單層索引
                    if isinstance(data.columns, pd.MultiIndex):
                        series = data[symbol]
                    else:
                        series = data[symbol]
                else:
                    series = data
                
                # 抓取最後一個有效值
                price = series.dropna().iloc[-1]
                latest_prices[key] = float(price)
            except:
                latest_prices[key] = 0.0
                
    except Exception as e:
        st.error(f"數據抓取失敗: {e}")

    # 抓取 ATH (歷史高點)
    try:
        hist = yf.Ticker("^TWII").history(period="5y")
        ath = float(hist['High'].max())
    except:
        ath = 32996.0

    return latest_prices, ath

# --- 3. 側邊欄設定 ---
with st.sidebar:
    st.header("⚙️ 數據控制台")
    
    # === A. 模式切換開關 ===
    use_manual = st.toggle("🛠️ 啟用「手動輸入股價」模式", value=False, help="如果覺得自動抓取的報價有誤或延遲，請開啟此開關手動修正")
    
    # === B. 獲取數據 ===
    if not use_manual:
        with st.spinner('連線 Yahoo Finance 更新中...'):
            auto_prices, ath_auto = get_market_data()
            st.success(f"數據更新時間: {datetime.now(pytz.timezone('Asia/Taipei')).strftime('%H:%M:%S')}")
    else:
        auto_prices = {}
        ath_auto = 32996.0

    # === C. 輸入表單 ===
    with st.form("holdings_form"):
        # 1. 大盤設定
        st.subheader("1. 市場位階")
        if use_manual:
            current_index = st.number_input("加權指數", value=31346.0, step=10.0)
            ath_index = st.number_input("歷史高點 (ATH)", value=32996.0, step=10.0)
        else:
            # 自動模式顯示數據 (不可改)
            current_index = auto_prices.get("INDEX", 0)
            ath_index = ath_auto
            st.metric("加權指數 (自動)", f"{current_index:,.0f}")
            st.metric("歷史高點 (自動)", f"{ath_index:,.0f}")
        
        # 計算 MDD
        if ath_index > 0:
            mdd_pct = ((ath_index - current_index) / ath_index) * 100
        else:
            mdd_pct = 0.0
        st.info(f"📉 MDD: -{mdd_pct:.2f}%")

        # 2. 持股設定
        st.subheader("2. 持股明細")
        
        # 定義 helper function 來決定預設值
        def get_val(key, default_price):
            return auto_prices.get(key, default_price) if not use_manual else default_price

        # --- 攻擊型 ---
        st.caption("🔴 攻擊型 (正二)")
        col_a1, col_a2 = st.columns([1, 1])
        with col_a1:
            p_675 = st.number_input("00675L 價", value=get_val("00675L", 185.0), disabled=not use_manual)
            p_631 = st.number_input("00631L 價", value=get_val("00631L", 466.0), disabled=not use_manual)
            p_670 = st.number_input("00670L 價", value=get_val("00670L", 157.0), disabled=not use_manual)
        with col_a2:
            s_675 = st.number_input("00675L 股", value=11000, step=1000)
            s_631 = st.number_input("00631L 股", value=331, step=100)
            s_670 = st.number_input("00670L 股", value=616, step=100)

        # --- 核心型 ---
        st.caption("🟡 核心型 (美股)")
        col_b1, col_b2 = st.columns([1, 1])
        with col_b1:
            p_662 = st.number_input("00662 價", value=get_val("00662", 102.0), disabled=not use_manual)
        with col_b2:
            s_662 = st.number_input("00662 股", value=25840, step=100)

        # --- 防禦型 ---
        st.caption("🟢 防禦型 (高息)")
        col_c1, col_c2 = st.columns([1, 1])
        with col_c1:
            p_713 = st.number_input("00713 價", value=get_val("00713", 52.0), disabled=not use_manual)
        with col_c2:
            s_713 = st.number_input("00713 股", value=66000, step=1000)

        # --- 子彈庫 ---
        st.caption("🔵 子彈庫 (債券)")
        col_d1, col_d2 = st.columns([1, 1])
        with col_d1:
            p_865 = st.number_input("00865B 價", value=get_val("00865B", 47.5), disabled=not use_manual)
            p_948 = st.number_input("00948B 價", value=get_val("00948B", 9.6), disabled=not use_manual)
        with col_d2:
            s_865 = st.number_input("00865B 股", value=10000, step=1000)
            s_948 = st.number_input("00948B 股", value=0, step=1000) # 預設剔除

        # --- 負債 ---
        st.subheader("3. 負債")
        loan_amount = st.number_input("質押借款 (O)", value=2350000, step=10000)
        
        submitted = st.form_submit_button("🔄 立即計算")

# --- 4. 運算引擎 ---

# A. 階梯策略
ladder_data = [
    {"MDD區間": "< 5%", "目標": 23, "位階": "Tier 1 (高位)"},
    {"MDD區間": "5%~10%", "目標": 23, "位階": "Tier 1 (警戒)"}, 
    {"MDD區間": "10%~25%", "目標": 28, "位階": "Tier 2 (初跌)"},
    {"MDD區間": "25%~40%", "目標": 33, "位階": "Tier 3 (主跌)"},
    {"MDD區間": "40%~50%", "目標": 40, "位階": "Tier 4 (恐慌)"},
    {"MDD區間": "> 50%", "目標": 50, "位階": "Tier 5 (毀滅)"},
]

# 判定位階
target_attack_ratio = 23.0 
current_tier_index = 0
if mdd_pct < 5.0: target_attack_ratio, current_tier_index = 23.0, 0
elif mdd_pct < 10.0: target_attack_ratio, current_tier_index = 23.0, 1
elif mdd_pct < 25.0: target_attack_ratio, current_tier_index = 28.0, 2
elif mdd_pct < 40.0: target_attack_ratio, current_tier_index = 33.0, 3
elif mdd_pct < 50.0: target_attack_ratio, current_tier_index = 40.0, 4
else: target_attack_ratio, current_tier_index = 50.0, 5
current_tier_name = ladder_data[current_tier_index]["位階"]

# B. 市值計算
v_675 = p_675 * s_675
v_631 = p_631 * s_631
v_670 = p_670 * s_670
v_662 = p_662 * s_662
v_713 = p_713 * s_713
v_865 = p_865 * s_865
v_948 = p_948 * s_948

val_attack = v_675 + v_631 + v_670
val_core = v_662
val_defense = v_713
val_ammo = v_865 + v_948
total_assets = val_attack + val_core + val_defense + val_ammo
net_assets = total_assets - loan_amount

# C. Beta 計算
beta_ws = (
    (v_675 * 1.6) + (v_631 * 1.6) + (v_670 * 2.0) +
    (v_713 * 0.6) + (v_662 * 1.0) +
    (v_865 * 0.0) + (v_948 * -0.1)
)
portfolio_beta = beta_ws / total_assets if total_assets > 0 else 0

# D. 關鍵比率
maintenance_ratio = (total_assets / loan_amount) * 100 if loan_amount > 0 else 999
loan_ratio = (loan_amount / total_assets) * 100 if total_assets > 0 else 0
current_attack_ratio = (val_attack / total_assets) * 100 if total_assets > 0 else 0

# E. 再平衡
gap = current_attack_ratio - target_attack_ratio
threshold = 3.0

# --- 5. 儀表板顯示 ---

# === 區塊一：戰略位階 ===
st.header("1. 動態戰略地圖")
c1, c2, c3 = st.columns([1, 1, 2])
c1.metric("📉 大盤 MDD", f"-{mdd_pct:.2f}%")
c2.metric("🎯 目標曝險", f"{target_attack_ratio:.0f}%", f"{current_tier_name}")
df_ladder = pd.DataFrame(ladder_data)
def highlight(row):
    return [f'background-color: #ffcccc' if row['位階'] == current_tier_name else '' for _ in row]
with c3:
    st.dataframe(df_ladder.style.apply(highlight, axis=1), hide_index=True, use_container_width=True)

st.divider()

# === 區塊二：核心數據 ===
st.header("2. 核心數據")
k1, k2, k3, k4 = st.columns(4)
k1.metric("💰 總市值", f"${total_assets:,.0f}", f"淨值: ${net_assets:,.0f}")
k2.metric("📉 Beta", f"{portfolio_beta:.2f}", "目標: 1.05~1.2")

t_color = "normal"
if maintenance_ratio < 250: t_color = "inverse"
elif maintenance_ratio < 300: t_color = "off"
k3.metric("🛡️ 維持率", f"{maintenance_ratio:.0f}%", "安全 > 300%", delta_color=t_color)

l_color = "normal"
if loan_ratio > 35: l_color = "inverse"
k4.metric("💳 負債比", f"{loan_ratio:.1f}%", "安全 < 35%", delta_color=l_color)

st.divider()

# === 區塊三：配置與指令 ===
st.header("3. 配置與指令")
c1, c2 = st.columns([2, 1])

with c1:
    chart_data = pd.DataFrame({
        '資產': ['攻擊 (正二)', '核心 (00662)', '防禦 (00713)', '子彈庫'],
        '市值': [val_attack, val_core, val_defense, val_ammo]
    })
    colors = {'攻擊 (正二)': '#FF4B4B', '核心 (00662)': '#FFD700', '防禦 (00713)': '#2E8B57', '子彈庫': '#87CEFA'}
    fig = px.pie(chart_data, values='市值', names='資產', color='資產', color_discrete_map=colors, hole=0.5)
    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(showlegend=False, margin=dict(t=0,b=0,l=0,r=0))
    st.plotly_chart(fig, use_container_width=True)

with c2:
    st.subheader("🤖 AI 戰略指令")
    
    # 雙重風控
    is_safe_t = maintenance_ratio >= 300
    is_safe_u = loan_ratio <= 35
    
    if maintenance_ratio < 250:
        st.error("⛔ **紅色警戒 (CRITICAL)**\n\n維持率危險！禁止買進，賣股還債。")
    elif (not is_safe_t) or (not is_safe_u):
        st.warning(f"🟠 **風險提示**\n\n結構不佳 (T={maintenance_ratio:.0f}%, U={loan_ratio:.1f}%)。\n禁止大幅加碼。")
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
            st.success(f"✅ **系統完美**\n\n財務健康，無偏離。\n持續持有。")
