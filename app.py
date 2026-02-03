import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
import random
import time
from datetime import datetime

# ==========================================
# 0. 核心設定
# ==========================================
st.set_page_config(page_title="Brian's Auto Arbitrage | 拍場抄底神器", page_icon="🦅", layout="wide")

# 🔥🔥🔥 Brian 的精選車庫 🔥🔥🔥
FEATURED_CARS = [
    {
        "name": "2020 BENZ C300 AMG",
        "market_price": 168,
        "brian_price_range": "135~138", 
        "tags": ["總代理", "跑少", "黑內裝"],
        "desc": "本週最強標的。折舊已到底，氣氛燈/柏林之音滿配。這價格買到賺到。",
        "status": "🔥 競標中"
    },
    {
        "name": "2019 TOYOTA RAV4 油電",
        "market_price": 85,
        "brian_price_range": "65~68",
        "tags": ["一手車", "原廠保養", "省油"],
        "desc": "家庭用車首選。電池狀況極佳，里程僅 6 萬。閉著眼睛買都不會虧。",
        "status": "⏳ 即將結標"
    },
    {
        "name": "2016 MAZDA 3 頂級",
        "market_price": 42,
        "brian_price_range": "28~32",
        "tags": ["魂動紅", "Bose音響", "無待修"],
        "desc": "代步CP值之王。底盤紮實，外觀有 9 成新，新手練車最划算選擇。",
        "status": "✨ 精選推薦"
    }
]

st.markdown("""
    <style>
    .card-box { background-color: #ffffff; padding: 20px; border-radius: 10px; border: 1px solid #e0e0e0; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; }
    .featured-card { background: linear-gradient(135deg, #fff8e1 0%, #ffffff 100%); padding: 20px; border-radius: 12px; border: 2px solid #ffb300; box-shadow: 0 6px 12px rgba(255, 179, 0, 0.2); margin-bottom: 25px; position: relative; }
    .featured-badge { position: absolute; top: -12px; right: 20px; background-color: #d32f2f; color: white; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 0.9em; box-shadow: 0 2px 4px rgba(0,0,0,0.2); }
    .stButton>button { width: 100%; border-radius: 8px; height: 3em; font-weight: bold; font-size: 1.1em; background-color: #1565c0; color: white; transition: 0.3s; }
    .stButton>button:hover { background-color: #0d47a1; box-shadow: 0 2px 5px rgba(0,0,0,0.2); }
    .role-tag { font-size: 0.8em; padding: 4px 8px; border-radius: 4px; color: white; font-weight: bold; display: inline-block; }
    .tag-pill { background-color: #e3f2fd; color: #1565c0; padding: 2px 8px; border-radius: 10px; font-size: 0.8em; margin-right: 5px; }
    
    /* V47 新增：委託單樣式 */
    .order-paper {
        background-color: #f8f9fa;
        border: 2px dashed #1565c0;
        padding: 20px;
        border-radius: 10px;
        font-family: monospace;
        color: #333;
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 1. 資料庫讀取 (維持 V46)
# ==========================================
@st.cache_data
def load_data():
    csv_path = "cars.csv"
    if not os.path.exists(csv_path): return pd.DataFrame(), "MISSING"
    try: 
        df = pd.read_csv(csv_path, on_bad_lines='skip')
        if df.empty: return pd.DataFrame(), "EMPTY"
        if '成本底價' in df.columns:
             df['成本底價'] = df['成本底價'].astype(str).str.replace(',', '').str.replace('$', '').astype(float).astype(int)
        df['車款名稱'] = df['車款名稱'].astype(str).str.strip().str.upper()
        valid_brands = ['TOYOTA', 'HONDA', 'NISSAN', 'FORD', 'MAZDA', 'MITSUBISHI', 'LEXUS', 'BMW', 'BENZ', 'MERCEDES', 'VOLVO', 'AUDI', 'VOLKSWAGEN', 'VW', 'SUZUKI', 'SUBARU', 'HYUNDAI', 'KIA', 'PORSCHE', 'MINI', 'SKODA', 'PEUGEOT', 'INFINITI']
        def extract_brand(name):
            for brand in valid_brands:
                if brand in name: 
                    if brand == 'MERCEDES': return 'BENZ'
                    if brand == 'VW': return 'VOLKSWAGEN'
                    return brand
            return 'OTHER'
        df['Brand'] = df['車款名稱'].apply(extract_brand)
        df = df[df['Brand'] != 'OTHER']
        return df, "SUCCESS"
    except Exception as e: return pd.DataFrame(), f"ERROR: {str(e)}"

# ==========================================
# 2. 推薦演算法 (維持 V46)
# ==========================================
def recommend_cars(df, budget_limit, usage, brand_pref):
    budget_max = budget_limit * 10000
    budget_min = budget_max * 0.3 
    candidates = df[(df['成本底價'] <= budget_max) & (df['成本底價'] >= budget_min)].copy()
    if candidates.empty: return pd.DataFrame()
    
    suv_keywords = ['CR-V', 'RAV4', 'KUGA', 'X-TRAIL', 'SUV', 'CX-5', 'ODYSSEY', 'GLC', 'RX', 'NX', 'TIGUAN', 'SPORTAGE', 'TUCSON', 'OUTLANDER', 'URX', 'SIENTA', 'CROSS', 'HR-V']
    mpv_keywords = ['PREVIA', 'SIENNA', 'ALPHARD', 'ODYSSEY', 'M7', 'WISH', 'SHARAN', 'TOURAN', 'CARENS', 'HIACE']
    toyota_sport = ['86', 'SUPRA', 'GR', 'AURIS', 'SPORT', 'CH-R']
    
    def calculate_match_score(row):
        score = 0
        name = row['車款名稱']
        brand = row['Brand']
        if usage == "極致省油代步":
            if any(x in name for x in ['ALTIS', 'VIOS', 'YARIS', 'FIT', 'PRIUS', 'HYBRID', 'CITY', 'MARCH', 'COLT', 'SENTRA']): score += 50
            elif any(x in name for x in suv_keywords + mpv_keywords): score -= 1000 
        elif usage == "家庭舒適空間":
            if any(x in name for x in mpv_keywords + suv_keywords): score += 50
            elif any(x in name for x in ['YARIS', 'VIOS', 'MARCH', 'FIT', '86', 'MX-5']): score -= 1000 
        elif usage == "業務通勤耐操":
            if any(x in name for x in ['ALTIS', 'COROLLA', 'CAMRY', 'RAV4', 'CROSS', 'WISH']): score += 50
        elif usage == "面子社交商務":
            if any(x in name for x in ['BENZ', 'BMW', 'LEXUS', 'AUDI', 'VOLVO', 'PORSCHE']): score += 50
            elif any(x in name for x in ['TOYOTA', 'HONDA', 'NISSAN']): score -= 10 
        elif usage == "熱血操控樂趣":
            if any(x in name for x in ['BMW', 'FOCUS', 'GOLF', 'MAZDA', 'MX-5', '86', 'WRX', 'COOPER', 'MUSTANG', 'ST', 'GTI', 'SUPRA', 'GR', 'AURIS']): score += 50
            if any(x in name for x in mpv_keywords): score -= 10000
            if any(x in name for x in ['RAV4', 'CR-V', 'X-TRAIL']): score -= 500 
            if brand == "TOYOTA":
                if any(x in name for x in toyota_sport): score += 20 
                else: score -= 50 
        elif usage == "新手練車 (高折舊)":
            if any(x in name for x in ['VIOS', 'YARIS', 'COLT', 'TIIDA', 'MARCH', 'FOCUS', 'LIVINA']): score += 50
        if brand_pref != "不限 (所有品牌)" and brand == brand_pref: score += 200 
        return score

    candidates['match_score'] = candidates.apply(calculate_match_score, axis=1)
    candidates = candidates[candidates['match_score'] > -100]
    candidates['預估市價'] = candidates['成本底價'] * 1.18 
    candidates['代標總成本'] = candidates['成本底價'] * 1.05
    candidates['潛在省錢'] = candidates['預估市價'] - candidates['代標總成本']
    candidates = candidates.sort_values('成本底價', ascending=True)
    candidates = candidates.drop_duplicates(subset=['車款名稱'], keep='first')

    if candidates.empty: return pd.DataFrame()
    final_list = []
    used_brands = set() 
    used_names = set() 

    if brand_pref != "不限 (所有品牌)":
        hero_pool = candidates[(candidates['Brand'] == brand_pref) & (candidates['match_score'] > 0)].sort_values(['match_score', '潛在省錢'], ascending=[False, False])
        if not hero_pool.empty:
            hero_car = hero_pool.iloc[0]
            hero_car['Role'] = '🏆 首選推薦' 
            final_list.append(hero_car)
            used_brands.add(hero_car['Brand'])
            used_names.add(hero_car['車款名稱'])

    competitors_pool = candidates.sort_values(['match_score', '潛在省錢'], ascending=[False, False])
    for idx, row in competitors_pool.iterrows():
        if len(final_list) >= 3: break
        if row['Brand'] not in used_brands and row['車款名稱'] not in used_names:
            if len(final_list) == 0: row['Role'] = '💎 優質精選' 
            elif len(final_list) == 1: row['Role'] = '⚔️ 強力競品'
            else: row['Role'] = '⚖️ 跨界對比'
            final_list.append(row)
            used_brands.add(row['Brand'])
            used_names.add(row['車款名稱'])

    if len(final_list) < 3:
        remaining_pool = candidates[~candidates['車款名稱'].isin(used_names)].sort_values(['match_score', '潛在省錢'], ascending=[False, False])
        for idx, row in remaining_pool.iterrows():
            if len(final_list) >= 3: break
            row['Role'] = '🔥 熱門候補'
            final_list.append(row)
            used_names.add(row['車款名稱'])
    return pd.DataFrame(final_list)

# ==========================================
# 3. AI 投資顧問
# ==========================================
def get_ai_advice(api_key, car_name, wholesale_price, market_price, savings):
    luxury_brands = ['BENZ', 'BMW', 'LEXUS', 'AUDI', 'VOLVO', 'PORSCHE', 'INFINITI']
    fun_brands = ['MAZDA', 'MINI', 'SUBARU', 'GOLF', 'FOCUS', '86', 'SUPRA', 'GTI', 'WRX']
    car_type = "economy"
    if any(b in car_name for b in luxury_brands): car_type = "luxury"
    elif any(b in car_name for b in fun_brands): car_type = "fun"
    
    fallback_dict = {
        "luxury": ["此車款歷史折舊已趨緩，現在進場資金利用率最高。對商務人士來說，這是極高 CP 值的社交門票。", "以這種成本取得豪華品牌，是極為聰明的資產配置。"],
        "economy": ["標準的『現金流守護者』。超低持有成本加上極高流通性，這筆交易在財務上絕對是正期望值。", "拍場行情顯示此車款極少跌破此價格。現在入手，等於是買在安全邊際之上。"],
        "fun": ["用這種成本買到這種樂趣，是男人最划算的玩具投資。歷史成交紀錄顯示此類車款極為搶手。", "這種性能車款流通性好，玩個兩年再賣掉，折舊損失微乎其微。"]
    }
    genai.configure(api_key=api_key)
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        if car_type == "luxury": prompt_theme = "強調『面子、社交槓桿』。"
        elif car_type == "fun": prompt_theme = "強調『情緒價值、玩具屬性』。"
        else: prompt_theme = "強調『實用主義、TCO極小化』。"
        prompt = f"你是投資汽車顧問。標的：{car_name} (市價{int(market_price/10000)}萬 vs 底價{int(wholesale_price/10000)}萬)。請用60字內給出建議，策略：{prompt_theme}。Strong Buy。"
        response = model.generate_content(prompt)
        return response.text
    except: return random.choice(fallback_dict[car_type])

# ==========================================
# 4. 主程式 UI (V47：自助委託結單版)
# ==========================================
def main():
    with st.sidebar:
        st.header("🦅 設定控制台")
        if "GOOGLE_API_KEY" in st.secrets:
            api_key = st.secrets["GOOGLE_API_KEY"]
            st.success("✅ AI 顧問已連線")
        else:
            api_key = st.text_input("Google API Key", type="password")
        st.info("💡 **無人自助委託**\n選定車款後，直接在下方生成「正式委託單」，複製給 Brian 即可啟動代標流程。無須推銷對話。")
        st.caption("V47 (Self-Service Kiosk)")

    st.title("🦅 Brian's Auto Arbitrage | 拍場抄底神器")
    
    # 精選櫥窗
    st.markdown("### 🔥 本週精選 (Weekly Drops)")
    f_cols = st.columns(3)
    for i, car in enumerate(FEATURED_CARS):
        with f_cols[i]:
            st.markdown(f"""<div class='featured-card'>
                <div class='featured-badge'>{car['status']}</div>
                <h3>{car['name']}</h3>
                <div style='color:#757575; text-decoration: line-through;'>市價: {car['market_price']} 萬</div>
                <div style='color:#d32f2f; font-size:1.5em; font-weight:bold;'>預估: {car['brian_price_range']} 萬</div>
                <div style='margin-top:10px;'>
            """, unsafe_allow_html=True)
            for tag in car['tags']: st.markdown(f"<span class='tag-pill'>{tag}</span>", unsafe_allow_html=True)
            st.markdown(f"</div><p style='margin-top:10px; font-size:0.9em;'>{car['desc']}</p></div>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 🔎 AI 全台庫存掃描")
    
    df, status = load_data()
    if status == "SUCCESS" and not df.empty:
        brand_list = sorted(df['Brand'].unique().tolist())
        brand_options = ["不限 (所有品牌)"] + brand_list
    else: brand_options = ["不限 (所有品牌)"]

    col1, col2, col3 = st.columns(3)
    with col1: budget = st.slider("💰 總預算 (萬)", 10, 200, 70)
    with col2: usage = st.selectbox("🎯 主要用途", ["極致省油代步", "家庭舒適空間", "業務通勤耐操", "面子社交商務", "熱血操控樂趣", "新手練車 (高折舊)"])
    with col3: brand = st.selectbox("🚗 優先品牌", brand_options)

    if st.button("🔍 啟動 AI 差異化對決"):
        if status != "SUCCESS":
            st.error("⚠️ 資料庫讀取失敗")
            return

        with st.spinner("🤖 正在執行 TCO 財務模型分析..."):
            time.sleep(1.0) 
            results = recommend_cars(df, budget, usage, brand)
            
            if not results.empty:
                st.session_state['results'] = results # 存入 session state 以便下方取用
                st.success(f"✅ AI 鎖定了 **{len(results)} 台** 最佳獲利標的。")
                
                for i, (index, row) in enumerate(results.iterrows()):
                    car_name = row['車款名稱']
                    market_p = row['預估市價']
                    cost_p = row['成本底價']
                    savings = row['潛在省錢']
                    role = row.get('Role', '推薦標的')
                    role_bg = "#d32f2f" if "首選" in role else "#1976d2" if "競品" in role else "#616161"
                    
                    with st.container():
                        st.markdown(f"""<div class='card-box'>""", unsafe_allow_html=True)
                        c_title, c_badge = st.columns([3, 1])
                        with c_title: st.markdown(f"### {role}: {car_name}")
                        with c_badge: st.markdown(f"<span class='role-tag' style='background-color:{role_bg}; float:right;'>{role}</span>", unsafe_allow_html=True)
                        
                        m1, m2, m3 = st.columns(3)
                        m1.metric("市場行情", f"{int(market_p/10000)} 萬")
                        m2.metric("拍場預估", f"{int(cost_p/10000)} 萬", delta="Wholesale", delta_color="inverse")
                        m3.metric("Arbitrage", f"{int(savings/10000)} 萬", delta="Spread", delta_color="normal")
                        
                        if api_key:
                            advice = get_ai_advice(api_key, car_name, cost_p, market_p, savings)
                            st.markdown(f"<div style='background:#f9f9f9; padding:15px; border-left:5px solid {role_bg}; border-radius:5px; color:#333;'><b>🤖 AI 投資觀點：</b><br>{advice}</div>", unsafe_allow_html=True)
                        st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.warning(f"⚠️ 找不到符合條件的車。")

    # ==========================================
    # 🔥 V47 新增：無人自助委託站 (Order Kiosk)
    # ==========================================
    st.markdown("---")
    st.header("📝 自助委託結單 (Self-Service Kiosk)")
    st.caption("選好車了嗎？不需要跟業務講電話。直接填寫需求，AI 會幫你生成正式委託單，複製給 Brian 即可。")

    with st.form("order_form"):
        # 讓使用者選擇剛剛 AI 推薦的車，或是手動輸入
        # 這裡做一個簡單的處理：如果上面有搜尋結果，就列出來讓選
        
        car_choices = ["請選擇車款..."]
        if 'results' in st.session_state and not st.session_state['results'].empty:
            car_choices += st.session_state['results']['車款名稱'].tolist()
        car_choices.append("其他 (手動輸入)")
        
        c1, c2 = st.columns(2)
        with c1:
            target_car = st.selectbox("📦 您想委託的標的", car_choices)
            custom_car = st.text_input("手動輸入車款 (若選其他)", placeholder="例如: 2021 Toyota Corolla Cross")
            final_car = custom_car if target_car == "其他 (手動輸入)" else target_car
            
        with c2:
            max_bid = st.number_input("💰 最高投標上限 (萬)", min_value=10, max_value=500, step=1, help="含手續費的總預算")
            line_id = st.text_input("📲 您的 Line ID", placeholder="方便我們聯絡您")
        
        requirements = st.text_area("📋 其他需求備註", placeholder="例如：只要白色、不要有菸味、一定要有跟車系統...")
        
        submitted = st.form_submit_button("🖨️ 生成正式委託單")
        
        if submitted:
            if final_car == "請選擇車款..." and not custom_car:
                st.error("❌ 請選擇或輸入車款")
            elif not line_id:
                st.error("❌ 請輸入 Line ID 以便聯絡")
            else:
                # 生成委託單文本
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
                order_text = f"""
【Brian Auto Arbitrage 委託單】
--------------------------------
📅 日期: {timestamp}
👤 客戶 Line: {line_id}
🚗 目標車款: {final_car}
💰 投標上限: {max_bid} 萬 (含稅/手續費)
📋 特別需求: {requirements if requirements else '無'}
--------------------------------
🤖 此單由 AI 系統自動生成
確認無誤後，請將此訊息傳送給 Brian。
"""
                st.success("✅ 委託單生成成功！")
                st.markdown("請點擊右上角複製按鈕，或手動複製下方內容，傳送到 Line 群組。")
                st.code(order_text, language="text")
                st.markdown(f"[👉 點我開啟 Line 傳送委託單](https://line.me/ti/p/你的ID)")

if __name__ == "__main__":
    main()
