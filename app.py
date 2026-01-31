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
# 1. 資料庫讀取
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
# 2. 推薦演算法 (V42核心：強制競品優先)
# ==========================================
def recommend_cars(df, budget_limit, usage, brand_pref):
    budget_max = budget_limit * 10000
    budget_min = budget_max * 0.3 
    
    candidates = df[
        (df['成本底價'] <= budget_max) & 
        (df['成本底價'] >= budget_min)
    ].copy()
    
    if candidates.empty: return pd.DataFrame()
    
    # 關鍵字庫
    suv_keywords = ['CR-V', 'RAV4', 'KUGA', 'X-TRAIL', 'SUV', 'CX-5', 'ODYSSEY', 'GLC', 'RX', 'NX', 'TIGUAN', 'SPORTAGE', 'TUCSON', 'OUTLANDER', 'URX', 'SIENTA', 'CROSS', 'HR-V']
    mpv_keywords = ['PREVIA', 'SIENNA', 'ALPHARD', 'ODYSSEY', 'M7', 'WISH', 'SHARAN', 'TOURAN', 'CARENS']
    toyota_sport = ['86', 'SUPRA', 'GR', 'AURIS', 'SPORT', 'CH-R']
    
    def calculate_match_score(row):
        score = 0
        name = row['車款名稱']
        brand = row['Brand']
        
        # --- 1. 用途邏輯 ---
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
        
        # --- 2. 品牌加分 ---
        if brand_pref != "不限 (所有品牌)" and brand == brand_pref:
            score += 200 
            
        return score

    candidates['match_score'] = candidates.apply(calculate_match_score, axis=1)
    
    # 這裡稍微放寬：如果是競品搜尋階段，我們會需要更多候選人
    candidates = candidates[candidates['match_score'] > -100] # 只過濾掉絕對不行的 (例如 Previa 跑車)

    # 計算財務
    candidates['預估市價'] = candidates['成本底價'] * 1.18 
    candidates['代標總成本'] = candidates['成本底價'] * 1.05
    candidates['潛在省錢'] = candidates['預估市價'] - candidates['代標總成本']

    candidates = candidates.sort_values('成本底價', ascending=True)
    candidates = candidates.drop_duplicates(subset=['車款名稱'], keep='first')

    if candidates.empty: return pd.DataFrame()

    final_list = []
    selected_names = [] # 用來記錄已選的車型，避免重複
    
    # === 階段一：鎖定首選 (Hero) ===
    if brand_pref != "不限 (所有品牌)":
        # 嚴格篩選：首選必須分數 > 0
        preferred_cars = candidates[(candidates['Brand'] == brand_pref) & (candidates['match_score'] > 0)].sort_values(['match_score', '潛在省錢'], ascending=[False, False])
        
        if not preferred_cars.empty:
            hero_car = preferred_cars.iloc[0]
            hero_car['Role'] = '🏆 首選推薦' 
            final_list.append(hero_car)
            selected_names.append(hero_car['車款名稱'])
            
            # === 階段二：死命找對手 (Challengers) ===
            # 目標：找到 2 台 Brand != brand_pref 的車
            
            # 1. 先找分數高 (>0) 的競品
            competitors_high = candidates[
                (candidates['Brand'] != brand_pref) & 
                (candidates['match_score'] > 0)
            ].sort_values(['match_score', '潛在省錢'], ascending=[False, False])
            
            for idx, row in competitors_high.iterrows():
                if len(final_list) >= 3: break
                row['Role'] = '⚔️ 強力競品'
                final_list.append(row)
                selected_names.append(row['車款名稱'])
            
            # 2. 如果湊不滿 3 台，放寬標準：找分數普普 (> -100) 的競品
            # 這一步是 V42 的關鍵：寧願推一台普通的 Mazda，也不要推第二台 Toyota
            if len(final_list) < 3:
                competitors_low = candidates[
                    (candidates['Brand'] != brand_pref) & 
                    (~candidates['車款名稱'].isin(selected_names))
                ].sort_values('潛在省錢', ascending=False) # 改用省錢金額排序，因為分數可能都很低
                
                for idx, row in competitors_low.iterrows():
                    if len(final_list) >= 3: break
                    row['Role'] = '⚖️ 跨界對比' # 換個稱號
                    final_list.append(row)
                    selected_names.append(row['車款名稱'])

    # === 階段三：還是湊不滿？ (Fallback) ===
    # 只有在真的找不到任何其他品牌的車時，才允許回頭找同品牌的車
    if len(final_list) < 3:
        remaining = candidates[~candidates['車款名稱'].isin(selected_names)].sort_values(['match_score', '潛在省錢'], ascending=[False, False])
        
        for idx, row in remaining.iterrows():
            if len(final_list) >= 3: break
            
            # V42 防呆：如果已經有同款車(例如 RAV4)，儘量不要再推 RAV4
            # 這裡簡單判斷：檢查車名最前面的單字 (例如 TOYOTA RAV4 -> RAV4)
            # 簡化版：直接允許，但給予不同稱號
            
            row['Role'] = '🔥 熱門候補'
            final_list.append(row)
            selected_names.append(row['車款名稱'])

    return pd.DataFrame(final_list)

# ==========================================
# 3. AI 投資顧問
# ==========================================
def get_ai_advice(api_key, car_name, wholesale_price, market_price, savings):
    luxury_brands = ['BENZ', 'BMW', 'LEXUS', 'AUDI', 'VOLVO', 'PORSCHE', 'INFINITI']
    fun_brands = ['MAZDA', 'MINI', 'SUBARU', 'GOLF', 'FOCUS', '86', 'SUPRA', 'GTI', 'WRX', 'COOPER']
    
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
            "別把錢浪費在會折舊的鐵皮上。這台車已經跌無可跌，是精明理財者的首選。"
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
        st.caption("V42 (Forced Diversity Edition)")

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

        with st.spinner("🤖 正在進行多品牌 TCO 對決... 尋找跨界競品..."):
            time.sleep(0.8) 
            
            results = recommend_cars(df, budget, usage, brand)
            
            if not results.empty:
                st.success(f"✅ 對決完成！AI 鎖定了 **{len(results)} 台** 不同定位的標的。")
                
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

