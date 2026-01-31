import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
import random
import time
import re

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
    /* 讓比較表格更清楚 */
    .vs-tag {
        background-color: #eeeeee;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8em;
        color: #666;
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

        # 品牌白名單
        valid_brands = [
            'TOYOTA', 'HONDA', 'NISSAN', 'FORD', 'MAZDA', 'MITSUBISHI', 'LEXUS', 
            'BMW', 'BENZ', 'MERCEDES', 'VOLVO', 'AUDI', 'VOLKSWAGEN', 'VW', 
            'SUZUKI', 'SUBARU', 'HYUNDAI', 'KIA', 'PORSCHE', 'MINI', 'SKODA', 'PEUGEOT'
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
# 2. 推薦演算法 (V38核心：差異化對決)
# ==========================================
def recommend_cars(df, budget_limit, usage, brand_pref):
    # 1. 基礎過濾 (預算)
    budget_max = budget_limit * 10000
    budget_min = budget_max * 0.3 
    
    candidates = df[
        (df['成本底價'] <= budget_max) & 
        (df['成本底價'] >= budget_min)
    ].copy()
    
    if candidates.empty: return pd.DataFrame()
    
    # 2. 用途計分 (維持 V37 邏輯)
    suv_keywords = ['CR-V', 'RAV4', 'KUGA', 'X-TRAIL', 'SUV', 'CX-5', 'ODYSSEY', 'GLC', 'RX', 'NX', 'TIGUAN', 'SPORTAGE', 'TUCSON', 'OUTLANDER', 'URX', 'SIENTA', 'CROSS', 'HR-V']
    
    def calculate_match_score(car_name):
        score = 0
        name = car_name
        
        if usage == "極致省油代步":
            if any(x in name for x in ['ALTIS', 'VIOS', 'YARIS', 'FIT', 'PRIUS', 'HYBRID', 'CITY', 'MARCH', 'COLT', 'SENTRA']): score += 10
            elif any(x in name for x in suv_keywords): score -= 5 
        elif usage == "家庭舒適空間":
            if any(x in name for x in suv_keywords + ['ODYSSEY', 'SIENNA', 'PREVIA', 'M7', 'WISH']): score += 10
            elif any(x in name for x in ['YARIS', 'VIOS', 'MARCH', 'FIT']): score -= 5 
        elif usage == "業務通勤耐操":
            if any(x in name for x in ['ALTIS', 'COROLLA', 'CAMRY', 'RAV4', 'CROSS', 'WISH']): score += 10
        elif usage == "面子社交商務":
            if any(x in name for x in ['BENZ', 'BMW', 'LEXUS', 'AUDI', 'VOLVO', 'PORSCHE']): score += 10
            elif any(x in name for x in ['TOYOTA', 'HONDA', 'NISSAN']): score -= 2
        elif usage == "熱血操控樂趣":
            if any(x in name for x in ['BMW', 'FOCUS', 'GOLF', 'MAZDA', 'MX-5', '86', 'WRX', 'COOPER', 'MUSTANG']): score += 10
            elif any(x in name for x in ['SUV', 'VAN']): score -= 5
        elif usage == "新手練車 (高折舊)":
            if any(x in name for x in ['VIOS', 'YARIS', 'COLT', 'TIIDA', 'MARCH', 'FOCUS', 'LIVINA']): score += 10
            
        return score

    candidates['match_score'] = candidates['車款名稱'].apply(calculate_match_score)
    candidates = candidates[candidates['match_score'] > 0] # 只留符合的
    
    # 計算財務數據
    candidates['預估市價'] = candidates['成本底價'] * 1.18 
    candidates['代標總成本'] = candidates['成本底價'] * 1.05
    candidates['潛在省錢'] = candidates['預估市價'] - candidates['代標總成本']

    # 去除重複車款 (保留最便宜的)
    candidates = candidates.sort_values('成本底價', ascending=True)
    candidates = candidates.drop_duplicates(subset=['車款名稱'], keep='first')

    if candidates.empty: return pd.DataFrame()

    # === V38 關鍵：差異化挑選邏輯 ===
    final_list = []
    
    # 策略 A: 如果使用者選了特定品牌
    if brand_pref != "不限 (所有品牌)":
        # 1. 優先推薦 (Hero Product)：從偏好品牌選 1 台分數最高的
        preferred_cars = candidates[candidates['Brand'] == brand_pref].sort_values(['match_score', '潛在省錢'], ascending=[False, False])
        if not preferred_cars.empty:
            hero_car = preferred_cars.iloc[0]
            hero_car['Role'] = '🏆 首選推薦'
            final_list.append(hero_car)
            
            # 2. 競爭對手 (Challengers)：從「非偏好品牌」選 2 台最強的
            other_cars = candidates[candidates['Brand'] != brand_pref].sort_values(['match_score', '潛在省錢'], ascending=[False, False])
            
            # 確保對手品牌不重複 (盡量)
            added_brands = set()
            for idx, row in other_cars.iterrows():
                if len(final_list) >= 3: break
                if row['Brand'] not in added_brands:
                    row['Role'] = '⚔️ 強力競品'
                    final_list.append(row)
                    added_brands.add(row['Brand'])
        else:
            # 如果偏好品牌沒車，就退回通用邏輯
            pass 

    # 策略 B: 如果使用者選不限，或是策略 A 沒湊滿 3 台
    if len(final_list) < 3:
        # 排除掉已經選入的車
        existing_ids = [x['車款名稱'] for x in final_list]
        remaining = candidates[~candidates['車款名稱'].isin(existing_ids)].sort_values(['match_score', '潛在省錢'], ascending=[False, False])
        
        # 盡量選不同品牌的
        added_brands = set([x['Brand'] for x in final_list])
        
        for idx, row in remaining.iterrows():
            if len(final_list) >= 3: break
            if row['Brand'] not in added_brands:
                row['Role'] = '💎 優質精選' if len(final_list) == 0 else '⚔️ 同級對比'
                final_list.append(row)
                added_brands.add(row['Brand'])
        
        # 如果還是湊不滿 (品牌太少)，就隨便填滿
        if len(final_list) < 3:
            for idx, row in remaining.iterrows():
                if len(final_list) >= 3: break
                if row['車款名稱'] not in [x['車款名稱'] for x in final_list]:
                    row['Role'] = '🔥 熱門候補'
                    final_list.append(row)

    return pd.DataFrame(final_list)

# ==========================================
# 3. AI 投資顧問 (V38核心：5種劇本隨機切換)
# ==========================================
def get_ai_advice(api_key, car_name, wholesale_price, market_price, savings):
    genai.configure(api_key=api_key)
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # 定義 5 種不同的分析角度 (劇本)
        scenarios = [
            # 劇本 1: 現金流大師
            f"""你是一位專注現金流的財務顧問。
            分析重點：強調「省下的 {int(savings/10000)} 萬」可以拿去做什麼投資 (例如美股 ETF、比特幣)。
            語氣：理智、數學導向。
            """,
            
            # 劇本 2: 反車商戰士
            f"""你是一位痛恨中間商賺差價的市場駭客。
            分析重點：強調車商賺這 {int(savings/10000)} 萬完全沒有道理，鼓勵使用者拿回主控權。
            語氣：犀利、革命性。
            """,
            
            # 劇本 3: 折舊精算師
            f"""你是一位專精二手車折舊曲線的數據分析師。
            分析重點：強調 {car_name} 目前的價格已經到了「折舊甜蜜點」，再跌也跌不到哪去。
            語氣：穩重、專業。
            """,
            
            # 劇本 4: 第一性原理 (工程師)
            f"""你是一位信奉第一性原理的工程師。
            分析重點：分析這台車的「實用價值」遠高於「市場溢價」，是一台純粹的交通工具，不含智商稅。
            語氣：硬核、邏輯。
            """,
            
            # 劇本 5: 抄底交易員
            f"""你是一位華爾街交易員。
            分析重點：現在這個價格是 "Undervalued" (被低估)，市場流動性高，必須立刻 "Execute" (執行)。
            語氣：急迫、簡潔。
            """
        ]
        
        # 隨機選一個劇本
        selected_scenario = random.choice(scenarios)
        
        prompt = f"""
        {selected_scenario}
        
        交易標的：{car_name}
        市價：{int(market_price/10000)} 萬
        拍場底價：{int(wholesale_price/10000)} 萬
        套利空間：{int(savings/10000)} 萬
        
        請給出 60 字以內的短評。不要講廢話，直接給結論 (Strong Buy)。
        """
        
        response = model.generate_content(prompt)
        return response.text
    except:
        return "AI 分析：數據顯示此車款目前位於折舊甜蜜點，拍場價格極具優勢。建議立即買入。"

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
        
        st.info("💡 **差異化推薦引擎**\n系統會優先尋找你偏好的品牌，並自動匹配其他品牌的同級車款進行「TCO 對比」，確保你做出最理性的選擇。")
        st.caption("V38 (Differentiation Edition)")

    st.title("🦅 Brian's Auto Arbitrage | 拍場抄底神器")
    st.markdown("""
    > **「不只要省錢，更要貨比三家。」**
    > AI 將為你鎖定一台 **首選推薦**，並尋找兩台 **強力競品** 進行殘酷的價格對決。
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
        budget = st.slider("💰 總預算 (萬)", 10, 150, 60)
    with col2:
        usage = st.selectbox("🎯 主要用途", [
            "極致省油代步", "家庭舒適空間", "業務通勤耐操", 
            "面子社交商務", "熱血操控樂趣", "新手練車 (高折舊)"
        ])
    with col3:
        brand = st.selectbox("🚗 優先品牌 (我們會找競品PK)", brand_options)

    if st.button("🔍 啟動 AI 差異化對決"):
        if status != "SUCCESS":
            st.error("⚠️ 資料庫讀取失敗")
            return

        with st.spinner("🤖 正在進行多品牌 TCO 對決... 生成 5 種投資觀點..."):
            time.sleep(1.0) 
            
            results = recommend_cars(df, budget, usage, brand)
            
            if not results.empty:
                st.success(f"✅ 對決完成！AI 鎖定了 **{len(results)} 台** 不同定位的標的。")
                
                for i, (index, row) in enumerate(results.iterrows()):
                    car_name = row['車款名稱']
                    market_p = row['預估市價']
                    cost_p = row['成本底價']
                    savings = row['潛在省錢']
                    role = row.get('Role', '推薦標的')
                    
                    # 根據角色換顏色
                    role_color = "#d32f2f" if "首選" in role else "#1976d2" if "競品" in role else "#f57c00"
                    
                    with st.container():
                        st.markdown(f"""<div class='card-box'>""", unsafe_allow_html=True)
                        
                        # 標題區 (加入角色標籤)
                        c_title, c_badge = st.columns([3, 1])
                        with c_title:
                            st.subheader(f"{role}: {car_name}")
                        with c_badge:
                             st.markdown(f"<div style='text-align:right; color:white; background-color:{role_color}; font-weight:bold; padding:5px; border-radius:5px;'>{role}</div>", unsafe_allow_html=True)
                        
                        # Metrics
                        m1, m2, m3 = st.columns(3)
                        m1.metric("市場行情", f"{int(market_p/10000)} 萬")
                        m2.metric("拍場底價", f"{int(cost_p/10000)} 萬", delta="Cost", delta_color="inverse")
                        m3.metric("Arbitrage", f"{int(savings/10000)} 萬", delta="Profit", delta_color="normal")
                        
                        # AI Advice (隨機劇本)
                        if api_key:
                            advice = get_ai_advice(api_key, car_name, cost_p, market_p, savings)
                            st.markdown(f"<div style='background:#f1f8e9; padding:15px; border-left:5px solid {role_color}; border-radius:5px; color:#33691e;'><b>🤖 AI 投資觀點：</b><br>{advice}</div>", unsafe_allow_html=True)
                        
                        st.markdown("---")
                        b1, b2 = st.columns([4, 1])
                        with b1:
                             # 這裡可以根據車子品牌做差異化描述
                            st.caption(f"📍 {row['Brand']} 原廠認證級別 | 流通性：高")
                        with b2:
                            st.markdown(f"[📲 索取代標報告](https://line.me/ti/p/你的ID)", unsafe_allow_html=True) 
                        
                        st.markdown("</div>", unsafe_allow_html=True)

            else:
                st.warning("⚠️ 此條件下無符合車款，請嘗試放寬預算。")

if __name__ == "__main__":
    main()
