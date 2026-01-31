import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
import random
import time

# ==========================================
# 0. 核心設定
# ==========================================
st.set_page_config(page_title="Brian's Auto Arbitrage | 拍場抄底神器", page_icon="🦅", layout="wide")

st.markdown("""
    <style>
    .card-box { 
        background-color: #ffffff; 
        padding: 20px; 
        border-radius: 10px; 
        border: 1px solid #e0e0e0; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    .stButton>button { 
        width: 100%; 
        border-radius: 8px; 
        height: 3em; 
        font-weight: bold; 
        font-size: 1.1em;
        background-color: #1565c0; 
        color: white;
    }
    .role-tag {
        font-size: 0.8em;
        padding: 4px 8px;
        border-radius: 4px;
        color: white;
        font-weight: bold;
        display: inline-block;
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 1. 資料庫讀取與清洗
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

        valid_brands = [
            'TOYOTA', 'HONDA', 'NISSAN', 'FORD', 'MAZDA', 'MITSUBISHI', 'LEXUS', 
            'BMW', 'BENZ', 'MERCEDES', 'VOLVO', 'AUDI', 'VOLKSWAGEN', 'VW', 
            'SUZUKI', 'SUBARU', 'HYUNDAI', 'KIA', 'PORSCHE', 'MINI', 'SKODA', 'PEUGEOT', 'INFINITI'
        ]
        
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
# 2. 推薦演算法 (V41核心：黑名單機制)
# ==========================================
def recommend_cars(df, budget_limit, usage, brand_pref):
    budget_max = budget_limit * 10000
    budget_min = budget_max * 0.3 
    
    candidates = df[
        (df['成本底價'] <= budget_max) & 
        (df['成本底價'] >= budget_min)
    ].copy()
    
    if candidates.empty: return pd.DataFrame()
    
    # 定義關鍵字庫
    suv_keywords = ['CR-V', 'RAV4', 'KUGA', 'X-TRAIL', 'SUV', 'CX-5', 'ODYSSEY', 'GLC', 'RX', 'NX', 'TIGUAN', 'SPORTAGE', 'TUCSON', 'OUTLANDER', 'URX', 'SIENTA', 'CROSS', 'HR-V']
    mpv_keywords = ['PREVIA', 'SIENNA', 'ALPHARD', 'ODYSSEY', 'M7', 'WISH', 'SHARAN', 'TOURAN', 'CARENS', 'HIACE']
    toyota_sport_keywords = ['86', 'SUPRA', 'GR', 'AURIS', 'SPORT', 'CH-R'] # 針對 Toyota 的運動化白名單
    
    def calculate_match_score(row):
        score = 0
        name = row['車款名稱']
        brand = row['Brand']
        
        # --- 1. 用途邏輯 (Logic Gates) ---
        
        if usage == "極致省油代步":
            if any(x in name for x in ['ALTIS', 'VIOS', 'YARIS', 'FIT', 'PRIUS', 'HYBRID', 'CITY', 'MARCH', 'COLT', 'SENTRA']): score += 50
            elif any(x in name for x in suv_keywords + mpv_keywords): score -= 1000 # 代步絕不推耗油大車
            
        elif usage == "家庭舒適空間":
            if any(x in name for x in mpv_keywords + suv_keywords): score += 50
            elif any(x in name for x in ['YARIS', 'VIOS', 'MARCH', 'FIT', '86', 'MX-5']): score -= 1000 # 家庭絕不推小車/跑車
            
        elif usage == "業務通勤耐操":
            if any(x in name for x in ['ALTIS', 'COROLLA', 'CAMRY', 'RAV4', 'CROSS', 'WISH']): score += 50
            
        elif usage == "面子社交商務":
            if any(x in name for x in ['BENZ', 'BMW', 'LEXUS', 'AUDI', 'VOLVO', 'PORSCHE']): score += 50
            elif any(x in name for x in ['TOYOTA', 'HONDA', 'NISSAN']): score -= 10 # 普通牌扣分
            
        elif usage == "熱血操控樂趣":
            # 正面表列
            if any(x in name for x in ['BMW', 'FOCUS', 'GOLF', 'MAZDA', 'MX-5', '86', 'WRX', 'COOPER', 'MUSTANG', 'ST', 'GTI', 'SUPRA', 'GR', 'AURIS']): score += 50
            # 負面表列 (V41重點：絕對殺掉 MPV/SUV)
            if any(x in name for x in mpv_keywords): score -= 10000 # Previa 殺手
            if any(x in name for x in ['RAV4', 'CR-V', 'X-TRAIL']): score -= 500 # 休旅車扣分
            
            # 針對 Toyota 的特殊處理
            if brand == "TOYOTA":
                if any(x in name for x in toyota_sport_keywords):
                    score += 20 # 額外加分給 86/Supra
                else:
                    score -= 50 # 如果是 Toyota 但不是運動款 (如 Altis 一般版)，扣分
            
        elif usage == "新手練車 (高折舊)":
            if any(x in name for x in ['VIOS', 'YARIS', 'COLT', 'TIIDA', 'MARCH', 'FOCUS', 'LIVINA']): score += 50
        
        # --- 2. 品牌忠誠度 (加分但不能蓋過黑名單) ---
        if brand_pref != "不限 (所有品牌)" and brand == brand_pref:
            # V41修正：只加 200 分，而不是 1000 分
            # 這樣如果上面被扣了 10000 分 (Previa)，加 200 分也救不回來
            score += 200 
            
        return score

    candidates['match_score'] = candidates.apply(calculate_match_score, axis=1)
    
    # 過濾：必須分數 > 0 才能入選
    # 這意味著 Previa 在熱血模式下 (-9800分) 會直接消失
    candidates = candidates[candidates['match_score'] > 0]

    # 計算財務
    candidates['預估市價'] = candidates['成本底價'] * 1.18 
    candidates['代標總成本'] = candidates['成本底價'] * 1.05
    candidates['潛在省錢'] = candidates['預估市價'] - candidates['代標總成本']

    # 去重
    candidates = candidates.sort_values('成本底價', ascending=True)
    candidates = candidates.drop_duplicates(subset=['車款名稱'], keep='first')

    if candidates.empty: return pd.DataFrame()

    final_list = []
    
    # === 策略 A: 絕對首選 (Hero) ===
    if brand_pref != "不限 (所有品牌)":
        preferred_cars = candidates[candidates['Brand'] == brand_pref].sort_values(['match_score', '潛在省錢'], ascending=[False, False])
        
        if not preferred_cars.empty:
            hero_car = preferred_cars.iloc[0]
            hero_car['Role'] = '🏆 首選推薦' 
            final_list.append(hero_car)
            
            # 找對手
            other_cars = candidates[candidates['Brand'] != brand_pref].sort_values(['match_score', '潛在省錢'], ascending=[False, False])
            added_brands = set()
            for idx, row in other_cars.iterrows():
                if len(final_list) >= 3: break
                if row['Brand'] not in added_brands:
                    row['Role'] = '⚔️ 強力競品'
                    final_list.append(row)
                    added_brands.add(row['Brand'])
    
    # === 策略 B: 通用邏輯 ===
    if len(final_list) == 0:
        candidates = candidates.sort_values(['match_score', '潛在省錢'], ascending=[False, False])
        added_brands = set()
        for idx, row in candidates.iterrows():
            if len(final_list) >= 3: break
            if row['Brand'] not in added_brands:
                row['Role'] = '💎 優質精選' if len(final_list) == 0 else '⚔️ 同級對比'
                final_list.append(row)
                added_brands.add(row['Brand'])
    
    if len(final_list) < 3 and not candidates.empty:
        existing_names = [x['車款名稱'] for x in final_list]
        remaining = candidates[~candidates['車款名稱'].isin(existing_names)].sort_values('match_score', ascending=False)
        for idx, row in remaining.iterrows():
             if len(final_list) >= 3: break
             row['Role'] = '🔥 熱門候補'
             final_list.append(row)

    return pd.DataFrame(final_list)

# ==========================================
# 3. AI 投資顧問 (維持 V40 多樣化邏輯)
# ==========================================
def get_ai_advice(api_key, car_name, wholesale_price, market_price, savings):
    luxury_brands = ['BENZ', 'BMW', 'LEXUS', 'AUDI', 'VOLVO', 'PORSCHE', 'INFINITI']
    fun_brands = ['MAZDA', 'MINI', 'SUBARU', 'GOLF', 'FOCUS', '86', 'SUPRA', 'GTI', 'WRX']
    
    car_type = "economy"
    if any(b in car_name for b in luxury_brands): car_type = "luxury"
    elif any(b in car_name for b in fun_brands): car_type = "fun"
    
    fallback_dict = {
        "luxury": [
            "這種車買的是『社交籌碼』。現在入手等於用國產車的價格買到談生意的門票，折舊已經由前一手幫你扛了。",
            "對於商務人士來說，這台車的 ROI (投報率) 極高。開出去的氣場遠超過它的拍場成本。",
            "這就是『資產配置』的魅力。把面子做足，裡子也省到了。省下的價差建議保留做為精緻養護基金。"
        ],
        "economy": [
            "這台車是標準的『現金流守護者』。超低的持有成本，買它就是為了把錢省下來去做更有意義的投資。",
            "代步車的真諦：省油、好養、不虧錢。拍場價格極具優勢，這筆交易絕對是正期望值。",
            "省下的這幾萬塊價差，足夠你加兩年的油加上換四條頂級輪胎。這才是真正的『懂車』。"
        ],
        "fun": [
            "買這台車買的是『情緒價值』。在拍場用這種價格入手樂趣車款，是男人最聰明的玩具投資。",
            "这种性能車款流通性好，現在抄底入手，玩個兩年再賣掉，搞不好還能小賺一筆。",
            "人生苦短，要開有趣的車。用這種成本買到這種操控樂趣，這筆交易本身就是一種享受。"
        ]
    }

    genai.configure(api_key=api_key)
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        if car_type == "luxury": prompt_theme = "強調『面子、社交槓桿』。告訴他用這種價格買到這種牌子是多麼精明的生意。"
        elif car_type == "fun": prompt_theme = "強調『情緒價值、玩具屬性』。告訴他花小錢買大樂趣是多划算。"
        else: prompt_theme = "強調『實用主義、TCO極小化』。告訴他省下的錢可以拿去買股票。"

        prompt = f"""
        你是一位投資型汽車顧問。標的：{car_name} (市價 {int(market_price/10000)}萬 vs 拍場 {int(wholesale_price/10000)}萬)。
        請用「簡短、犀利、中肯」的語氣 (60字內) 給出建議：
        核心策略：{prompt_theme}
        禁止廢話，直接給出 Strong Buy 的理由。
        """
        response = model.generate_content(prompt)
        return response.text
    except:
        return random.choice(fallback_dict[car_type])

# ==========================================
# 4. 主程式 UI
# ==========================================
def main():
    with st.sidebar:
        st.header("🦅 設定控制台")
        if "GOOGLE_API_KEY" in st.secrets:
            api_key = st.secrets["GOOGLE_API_KEY"]
            st.success("✅ AI 顧問已連線")
        else:
            api_key = st.text_input("Google API Key", type="password")
        
        st.info("💡 **差異化推薦引擎**\n系統會優先尋找你偏好的品牌，並自動匹配其他品牌的同級車款進行「TCO 對比」。")
        st.caption("V41 (Logic Gate Edition)")

    st.title("🦅 Brian's Auto Arbitrage | 拍場抄底神器")
    st.markdown("""
    > **「不只要省錢，更要買對價值。」**
    > AI 將鎖定一台 **首選推薦**，並尋找兩台 **強力競品** 進行殘酷的價格對決。
    """)
    st.markdown("---")

    df, status = load_data()
    
    if status == "SUCCESS" and not df.empty:
        brand_list = sorted(df['Brand'].unique().tolist())
        brand_options = ["不限 (所有品牌)"] + brand_list
    else:
        brand_options = ["不限 (所有品牌)"]

    col1, col2, col3 = st.columns(3)
    with col1:
        # V41: 稍微拉高預算上限，因為熱血車款通常比較貴 (例如 86/Supra)
        budget = st.slider("💰 總預算 (萬)", 10, 200, 70)
    with col2:
        usage = st.selectbox("🎯 主要用途", [
            "極致省油代步", "家庭舒適空間", "業務通勤耐操", 
            "面子社交商務", "熱血操控樂趣", "新手練車 (高折舊)"
        ])
    with col3:
        brand = st.selectbox("🚗 優先品牌", brand_options)

    if st.button("🔍 啟動 AI 差異化對決"):
        if status != "SUCCESS":
            st.error("⚠️ 資料庫讀取失敗")
            return

        with st.spinner("🤖 正在進行多品牌 TCO 對決... 剔除不符需求車款..."):
            time.sleep(0.8) 
            
            results = recommend_cars(df, budget, usage, brand)
            
            if not results.empty:
                st.success(f"✅ 對決完成！AI 鎖定了 **{len(results)} 台** 符合「{usage}」的最佳標的。")
                
                for i, (index, row) in enumerate(results.iterrows()):
                    car_name = row['車款名稱']
                    market_p = row['預估市價']
                    cost_p = row['成本底價']
                    savings = row['潛在省錢']
                    role = row.get('Role', '推薦標的')
                    
                    role_bg = "#d32f2f" if "首選" in role else "#1976d2" if "競品" in role else "#f57c00"
                    
                    with st.container():
                        st.markdown(f"""<div class='card-box'>""", unsafe_allow_html=True)
                        
                        c_title, c_badge = st.columns([3, 1])
                        with c_title:
                            st.markdown(f"### {role}: {car_name}")
                        with c_badge:
                             st.markdown(f"<span class='role-tag' style='background-color:{role_bg}; float:right;'>{role}</span>", unsafe_allow_html=True)
                        
                        m1, m2, m3 = st.columns(3)
                        m1.metric("市場行情", f"{int(market_p/10000)} 萬")
                        m2.metric("拍場底價", f"{int(cost_p/10000)} 萬", delta="Cost", delta_color="inverse")
                        m3.metric("Arbitrage", f"{int(savings/10000)} 萬", delta="Profit", delta_color="normal")
                        
                        if api_key:
                            advice = get_ai_advice(api_key, car_name, cost_p, market_p, savings)
                            border_color = role_bg
                            st.markdown(f"<div style='background:#f9f9f9; padding:15px; border-left:5px solid {border_color}; border-radius:5px; color:#333;'><b>🤖 AI 投資觀點：</b><br>{advice}</div>", unsafe_allow_html=True)
                        
                        st.markdown("---")
                        b1, b2 = st.columns([4, 1])
                        with b1:
                            st.caption(f"📍 {row['Brand']} 原廠認證級別 | 流通性：高")
                        with b2:
                            st.markdown(f"[📲 索取代標報告](https://line.me/ti/p/你的ID)", unsafe_allow_html=True) 
                        
                        st.markdown("</div>", unsafe_allow_html=True)

            else:
                st.warning(f"⚠️ 找不到符合條件的車。原因：你的預算內可能沒有「{brand}」的「{usage}」車款。建議放寬品牌或增加預算。")

if __name__ == "__main__":
    main()
