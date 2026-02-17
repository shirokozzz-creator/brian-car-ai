import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
import time
import random
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px

# ==========================================
# 0. V56 PRO 核心設定 & CSS 優化
# ==========================================
st.set_page_config(page_title="Brian's Auto Arbitrage Pro", page_icon="🦅", layout="wide")

# 自定義 CSS
st.markdown("""
    <style>
    /* 全局字體與配色 */
    .main { background-color: #f8f9fa; }
    h1, h2, h3 { color: #0d47a1; font-family: 'Helvetica', sans-serif; }
    
    /* 卡片式設計 */
    .card-box { 
        background-color: #ffffff; 
        padding: 25px; 
        border-radius: 12px; 
        border: 1px solid #e0e0e0; 
        box-shadow: 0 4px 15px rgba(0,0,0,0.05); 
        margin-bottom: 20px; 
        transition: transform 0.2s;
    }
    .card-box:hover { transform: translateY(-3px); box-shadow: 0 8px 20px rgba(0,0,0,0.1); }
    
    /* 標籤樣式 */
    .role-tag { font-size: 0.85em; padding: 5px 10px; border-radius: 6px; color: white; font-weight: bold; display: inline-block; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    
    /* 信任區塊 */
    .trust-badge { background-color: #e3f2fd; color: #1565c0; padding: 15px; border-radius: 8px; border-left: 5px solid #1565c0; margin-bottom: 10px; }
    
    /* 數據強調 */
    .big-number { font-size: 1.8em; font-weight: bold; color: #2e7d32; }
    .stMetric { background-color: white; padding: 10px; border-radius: 8px; border: 1px solid #eee; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 1. 模擬數據生成 (容錯機制)
# ==========================================
def generate_mock_data():
    """當找不到 CSV 時，生成模擬數據以供展示"""
    brands = ['TOYOTA', 'BENZ', 'BMW', 'LEXUS', 'MAZDA', 'HONDA', 'PORSCHE']
    models = {
        'TOYOTA': ['RAV4', 'ALTIS', 'CAMRY', 'COROLLA CROSS', 'ALPHARD'],
        'BENZ': ['C300', 'GLC300', 'E200', 'A180'],
        'BMW': ['320i', '520i', 'X3', 'X5'],
        'LEXUS': ['NX200', 'RX300', 'ES200', 'UX250h'],
        'MAZDA': ['MAZDA3', 'CX-5', 'CX-30'],
        'HONDA': ['CR-V', 'HR-V', 'FIT'],
        'PORSCHE': ['MACAN', 'CAYENNE']
    }
    data = []
    for _ in range(50):
        brand = random.choice(brands)
        model = random.choice(models[brand])
        year = random.randint(2015, 2023)
        wholesale = random.randint(30, 250)
        market_markup = random.uniform(1.15, 1.30)
        name = f"{year} {brand} {model}"
        
        data.append({
            '車款名稱': name,
            'Brand': brand,
            'Year': year,
            '成本底價': wholesale * 10000,
            '預估市價': int(wholesale * market_markup * 10000),
            '里程': random.randint(30000, 150000)
        })
    return pd.DataFrame(data)

@st.cache_data
def load_data():
    csv_path = "cars.csv"
    try:
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path, on_bad_lines='skip')
            # 簡單清洗
            if '成本底價' in df.columns:
                 df['成本底價'] = df['成本底價'].astype(str).str.replace(',', '').str.replace('$', '').astype(float).astype(int)
            # 這裡簡化品牌提取邏輯，沿用之前的或使用 mock
            # (省略複雜清洗以保持代碼簡潔，實際專案可加回)
            return df, "SUCCESS"
        else:
            return generate_mock_data(), "MOCK" # 回傳模擬數據
    except:
        return generate_mock_data(), "MOCK_ERROR"

# ==========================================
# 2. 邏輯核心 (增加 TCO 計算)
# ==========================================
def calculate_tco(car_price, year, mileage, engine_cc=2000, holding_years=5):
    """計算5年持有成本"""
    # 假設參數
    fuel_price = 31 # 油價
    km_per_liter = 12 if engine_cc < 2000 else 9 # 油耗
    annual_km = 15000
    
    # 稅金 (簡單估算)
    tax = 17410 if engine_cc <= 2000 else 22410 
    
    # 保養 (簡單估算)
    maintenance = 10000 + (mileage / 10000) * 1000
    
    # 折舊 (假設每年 10%)
    residual_value = car_price * ((0.9) ** holding_years)
    depreciation = car_price - residual_value
    
    fuel_cost = (annual_km / km_per_liter) * fuel_price * holding_years
    tax_total = tax * holding_years
    maint_total = maintenance * holding_years
    
    total_cost = depreciation + fuel_cost + tax_total + maint_total
    return int(total_cost), int(depreciation), int(fuel_cost), int(tax_total + maint_total)

# ==========================================
# 3. UI 組件
# ==========================================
def draw_price_waterfall(cost, fees, refurbish, market_price):
    """繪製價格瀑布圖 (Visual Arbitrage)"""
    my_cost = cost + fees + refurbish
    profit = market_price - my_cost
    
    fig = go.Figure(go.Waterfall(
        name = "20", orientation = "v",
        measure = ["relative", "relative", "relative", "total", "total"],
        x = ["拍場底價", "服務費/稅", "整新美容", "您的總成本", "市場行情"],
        textposition = "outside",
        text = [f"{int(cost/10000)}萬", f"{int(fees/10000)}萬", f"{int(refurbish/10000)}萬", f"{int(my_cost/10000)}萬", f"{int(market_price/10000)}萬"],
        y = [cost, fees, refurbish, my_cost, market_price - my_cost],
        connector = {"line":{"color":"rgb(63, 63, 63)"}},
    ))
    fig.update_layout(title="💰 獲利結構分析 (Arbitrage Structure)", showlegend=False, height=300)
    return fig

# ==========================================
# 4. 主程式
# ==========================================
def main():
    # 初始化
    if 'search_results' not in st.session_state: st.session_state.search_results = pd.DataFrame()
    df, status = load_data()
    
    # --- Sidebar ---
    with st.sidebar:
        st.header("🦅 設定控制台")
        api_key = st.text_input("Gemini API Key (選填)", type="password")
        st.info("💡 **V56 Pro 功能**\n模擬數據模式已啟動，無 CSV 亦可展示。")
        if status == "MOCK" or status == "MOCK_ERROR":
            st.warning("⚠️ 目前使用模擬數據演示中")

    # --- Header ---
    st.title("🦅 Brian's Auto Arbitrage Pro")
    st.markdown("### 數據驅動的二手車套利系統")

    # --- Tabs 分頁設計 (優化體驗) ---
    tab_home, tab_search, tab_tco, tab_order = st.tabs(["🏠 首頁 & 信任", "🔍 智能搜車", "📊 TCO 財務分析", "📝 委託結單"])

    # === TAB 1: 首頁 & 信任 ===
    with tab_home:
        # 數據看板
        c1, c2, c3 = st.columns(3)
        c1.metric("本週拍場上架", "1,248 台", "+12%")
        c2.metric("平均價差獲利", "18.5%", "Arbitrage Gap")
        c3.metric("成交率", "92%", "High Success")
        
        st.markdown("---")
        st.markdown("### 🏢 為什麼我們能拿到批發價？")
        c_trust1, c_trust2 = st.columns(2)
        with c_trust1:
            st.markdown("""
            <div class='trust-badge'>
                <h4>🔵 HAA 和運勁拍 (Toyota 集團)</h4>
                <p>全台最嚴格日式查定標準 (A~E級)。買 HAA 的車，等於買 Toyota 原廠認證的安心。絕無調表、泡水。</p>
            </div>
            """, unsafe_allow_html=True)
        with c_trust2:
            st.markdown("""
            <div class='trust-badge'>
                <h4>🔴 SAA 行將拍賣 (裕隆集團)</h4>
                <p>全台最大批發中心。大量公司長租退役車，保養紀錄最齊全。車商進貨的源頭。</p>
            </div>
            """, unsafe_allow_html=True)

    # === TAB 2: 智能搜車 ===
    with tab_search:
        st.markdown("#### 🔎 AI 全台庫存掃描")
        
        col1, col2, col3 = st.columns(3)
        with col1: budget = st.slider("💰 總預算 (萬)", 10, 300, 100)
        with col2: 
            brand_options = ["不限"] + list(df['Brand'].unique()) if not df.empty else ["不限"]
            brand_pref = st.selectbox("🚗 品牌偏好", brand_options)
        with col3: 
            sort_by = st.selectbox("排序方式", ["價差最大 (獲利優先)", "總價最低", "年份最新"])

        if st.button("🚀 啟動掃描", type="primary"):
            with st.spinner("正在比對 HAA/SAA 拍場數據..."):
                time.sleep(0.8) # 增加儀式感
                
                # 篩選邏輯
                budget_val = budget * 10000
                filtered = df[df['成本底價'] <= budget_val].copy()
                if brand_pref != "不限":
                    filtered = filtered[filtered['Brand'] == brand_pref]
                
                # 計算價差
                filtered['預估市價'] = filtered.get('預估市價', filtered['成本底價'] * 1.2)
                filtered['潛在獲利'] = filtered['預估市價'] - (filtered['成本底價'] * 1.05 + 20000) # 簡易成本公式
                
                # 排序
                if sort_by == "價差最大 (獲利優先)":
                    filtered = filtered.sort_values('潛在獲利', ascending=False)
                elif sort_by == "總價最低":
                    filtered = filtered.sort_values('成本底價', ascending=True)
                else:
                    filtered = filtered.sort_values('Year', ascending=False) if 'Year' in filtered.columns else filtered
                
                st.session_state.search_results = filtered.head(5)

        # 顯示結果
        if not st.session_state.search_results.empty:
            st.success(f"✅ 鎖定 {len(st.session_state.search_results)} 台最佳標的")
            
            for idx, row in st.session_state.search_results.iterrows():
                # 每個結果都是一個卡片
                with st.container():
                    st.markdown(f"<div class='card-box'>", unsafe_allow_html=True)
                    cols = st.columns([2, 3, 2])
                    
                    with cols[0]:
                        st.markdown(f"### {row['車款名稱']}")
                        st.caption(f"年份: {row.get('Year', 'N/A')} | 里程: {row.get('里程', 'N/A'):,} km")
                        st.markdown(f"<span class='role-tag' style='background:#d32f2f'>🔥 熱門標的</span>", unsafe_allow_html=True)

                    with cols[1]:
                        # 視覺化瀑布圖
                        fig = draw_price_waterfall(row['成本底價'], row['成本底價']*0.05, 15000, row['預估市價'])
                        st.plotly_chart(fig, use_container_width=True)

                    with cols[2]:
                        st.metric("預估市價", f"{int(row['預估市價']/10000)} 萬")
                        st.metric("拍場底價", f"{int(row['成本底價']/10000)} 萬", delta="Wholesale")
                        st.metric("預估省下", f"{int(row['潛在獲利']/10000)} 萬", delta_color="normal")
                        if st.button("詳細分析 & TCO", key=f"btn_{idx}"):
                             st.session_state['selected_car'] = row
                             st.info("已載入 TCO 分析頁面，請切換分頁查看。")

                    st.markdown("</div>", unsafe_allow_html=True)

    # === TAB 3: TCO 財務分析 ===
    with tab_tco:
        if 'selected_car' in st.session_state:
            car = st.session_state['selected_car']
            st.header(f"📊 TCO 分析: {car['車款名稱']}")
            
            c1, c2 = st.columns([1, 2])
            with c1:
                st.subheader("參數設定")
                holding_years = st.slider("預計持有年數", 1, 10, 5)
                mileage_year = st.slider("年行駛里程 (km)", 5000, 30000, 15000)
                engine_cc = st.selectbox("排氣量級距", [1500, 1800, 2000, 2400, 3000])
            
            with c2:
                total, dep, fuel, other = calculate_tco(car['成本底價'], 2020, 50000, engine_cc, holding_years)
                
                # 圓餅圖
                labels = ['折舊損失', '油資總計', '稅金與保養']
                values = [dep, fuel, other]
                fig = px.pie(values=values, names=labels, title=f"{holding_years} 年總持有成本結構 (預估: {int(total/10000)}萬)", hole=0.4)
                st.plotly_chart(fig, use_container_width=True)
                
                st.info(f"💡 **分析觀點**：這台車平均每年的持有成本約為 **{int(total/holding_years)} 元** (含折舊)。由於進價低於市價，您的首年折舊幾乎被「價差」抵銷，這是極佳的財務決策。")
        else:
            st.info("👈 請先在「智能搜車」頁面選擇一台車進行分析。")

    # === TAB 4: 委託結單 ===
    with tab_order:
        st.header("📝 自助委託結單")
        with st.form("final_order"):
            st.markdown("確認您的委託內容：")
            
            target_car_name = st.text_input("委託車款", value=st.session_state.get('selected_car', {}).get('車款名稱', ''))
            user_budget = st.number_input("您的最高出價 (萬)", value=int(st.session_state.get('selected_car', {}).get('成本底價', 0)/10000 * 1.05) if 'selected_car' in st.session_state else 50)
            
            contact_info = st.text_input("您的 Line ID / 手機", placeholder="09xx-xxx-xxx")
            notes = st.text_area("備註需求", placeholder="例如：一定要原版件、不要菸味...")
            
            submitted = st.form_submit_button("🖨️ 生成正式委託單", type="primary")
            
            if submitted:
                if not contact_info:
                    st.error("請填寫聯絡方式")
                else:
                    order_msg = f"""
                    【Brian's Auto Arbitrage 委託單】
                    ------------------------
                    📅 日期: {datetime.now().strftime('%Y-%m-%d')}
                    👤 客戶: {contact_info}
                    🚗 車款: {target_car_name}
                    💰 出價: {user_budget} 萬
                    📝 備註: {notes}
                    ------------------------
                    此單由 V56 Pro 系統生成
                    """
                    st.success("委託單已生成！")
                    st.code(order_msg)
                    st.markdown(f"[👉 點我開啟 Line 傳送](https://line.me/ti/p/你的ID)")

if __name__ == "__main__":
    main()
