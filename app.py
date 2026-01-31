import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
import random
import time
import re

# ==========================================
# 0. 核心設定 (專業投資風格)
# ==========================================
st.set_page_config(page_title="Brian's Auto Arbitrage | 拍場抄底神器", page_icon="🦅", layout="wide")

# --- CSS 美化 ---
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
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 1. 資料庫讀取與清洗 (V37 重點優化)
# ==========================================
@st.cache_data
def load_data():
    csv_path = "cars.csv"
    if not os.path.exists(csv_path): return pd.DataFrame(), "MISSING"
    try: 
        df = pd.read_csv(csv_path, on_bad_lines='skip')
        if df.empty: return pd.DataFrame(), "EMPTY"
        
        # 1. 價格轉數字
        if '成本底價' in df.columns:
             df['成本底價'] = df['成本底價'].astype(str).str.replace(',', '').str.replace('$', '').astype(float).astype(int)
        
        # 2. 車名標準化 (轉大寫，移除前後空白)
        df['車款名稱'] = df['車款名稱'].astype(str).str.strip().str.upper()

        # 3. 提取品牌 (V37修正：使用白名單匹配，解決亂碼問題)
        # 定義常見品牌庫
        valid_brands = [
            'TOYOTA', 'HONDA', 'NISSAN', 'FORD', 'MAZDA', 'MITSUBISHI', 'LEXUS', 
            'BMW', 'BENZ', 'MERCEDES', 'VOLVO', 'AUDI', 'VOLKSWAGEN', 'VW', 
            'SUZUKI', 'SUBARU', 'HYUNDAI', 'KIA', 'PORSCHE', 'MINI', 'SKODA', 'PEUGEOT'
        ]
        
        def extract_brand(name):
            for brand in valid_brands:
                if brand in name: # 如果車名包含品牌關鍵字
                    if brand == 'MERCEDES': return 'BENZ' # 統一賓士名稱
                    if brand == 'VW': return 'VOLKSWAGEN'
                    return brand
            return 'OTHER' # 找不到就歸類為其他

        df['Brand'] = df['車款名稱'].apply(extract_brand)
        
        # 過濾掉 'OTHER' 的雜訊 (如果不想要顯示奇怪的車)
        df = df[df['Brand'] != 'OTHER']

        return df, "SUCCESS"
    except Exception as e: return pd.DataFrame(), f"ERROR: {str(e)}"

# ==========================================
# 2. 推薦演算法 (V37修正：去重複)
# ==========================================
def recommend_cars(df, budget_limit, usage, brand_pref):
    # 1. 預算篩選
    budget_max = budget_limit * 10000
    budget_min = budget_max * 0.3 
    
    candidates = df[
        (df['成本底價'] <= budget_max) & 
        (df['成本底價'] >= budget_min)
    ].copy()
    
    if candidates.empty: return pd.DataFrame() 
    
    # 2. 品牌篩選 (使用清洗後的 Brand 欄位)
    if brand_pref != "不限 (所有品牌)":
        candidates = candidates[candidates['Brand'] == brand_pref]
        if candidates.empty: return pd.DataFrame()
    
    # 3. 用途邏輯 (根據車型關鍵字給分)
    suv_keywords = ['CR-V', 'RAV4', 'KUGA', 'X-TRAIL', 'SUV', 'CX-5', 'ODYSSEY', 'GLC', 'RX', 'NX', 'TIGUAN', 'SPORTAGE', 'TUCSON', 'OUTLANDER', 'URX', 'SIENTA', 'CROSS', 'HR-V']
    
    def calculate_match_score(car_name):
        score = 0
        name = car_name # 已經轉大寫了
        
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
    
    # 只留分數 > 0 的 (除非沒車)
    high_score = candidates[candidates['match_score'] > 0]
    if not high_score.empty:
        candidates = high_score

    # === V37 關鍵修正：去重複 ===
    # 按照價格排序，然後針對「車款名稱」去除重複，保留最便宜的那台
    candidates = candidates.sort_values('成本底價', ascending=True)
    candidates = candidates.drop_duplicates(subset=['車款名稱'], keep='first')

    # 4. 計算潛在利潤
    candidates['預估市價'] = candidates['成本底價'] * 1.18 
    candidates['代標總成本'] = candidates['成本底價'] * 1.05
    candidates['潛在省錢'] = candidates['預估市價'] - candidates['代標總成本']
    
    # 5. 最終排序 (取前 3 名)
    recommendations = candidates.sort_values(
        ['match_score', '潛在省錢'], ascending=[False, False]
    ).head(3) 
    
    return recommendations

# ==========================================
# 3. AI 投資顧問 (馬斯克中肯版)
# ==========================================
def get_ai_advice(api_key, car_name, wholesale_price, market_price, savings):
    genai.configure(api_key=api_key)
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        你現在是 Elon Musk，請以「資深投資人」的角度給出購車建議。
        
        標的：{car_name}
        市價：{int(market_price/10000)} 萬
        拍場底價：{int(wholesale_price/10000)} 萬
        套利空間：{int(savings/10000)} 萬
        
        請用「簡短、數據導向」的語氣 (80字以內) 回答：
        1. 擁車成本 (TCO) 分析優勢？
        2. 這筆交易的投報率？(例如：省下的錢可付幾年稅金)
        3. 給出決策指令 (Strong Buy)。
        禁止搞笑，專注於價值分析。
        """
        
        response = model.generate_content(prompt)
        return response.text
    except:
        return "AI 分析：數據顯示此車款目前位於折舊甜蜜點，拍場價格極具優勢。省下的價差足以支付首年乙式全險與稅金，建議立即買入。"

# ==========================================
# 4. 主程式 UI
# ==========================================
def main():
    # --- Sidebar ---
    with st.sidebar:
        st.header("🦅 設定控制台")
        if "GOOGLE_API_KEY" in st.secrets:
            api_key = st.secrets["GOOGLE_API_KEY"]
            st.success("✅ AI 顧問已連線")
        else:
            api_key = st.text_input("Google API Key", type="password")
        
        st.info("💡 **拍場抄底原理**\n我們直接掃描全台批發拍場庫存，跳過車商利潤，讓你用接近車行的成本入手好車。")
        st.caption("V37 (Clean Data Edition)")

    # --- Main ---
    st.title("🦅 Brian's Auto Arbitrage | 拍場抄底神器")
    st.markdown("""
    > **「買車不該是消費，而是一場精計算的資產配置。」**
    > 輸入條件，AI 幫你找出目前市場上 **被低估、具備高套利空間** 的優質標的。
    """)
    st.markdown("---")

    # 載入並清洗資料
    df, status = load_data()
    
    # 準備品牌選單 (從清洗後的 Brand 欄位抓取)
    if status == "SUCCESS" and not df.empty:
        brand_list = sorted(df['Brand'].unique().tolist())
        brand_options = ["不限 (所有品牌)"] + brand_list
    else:
        brand_options = ["不限 (所有品牌)"]

    # 輸入區
    col1, col2, col3 = st.columns(3)
    
    with col1:
        budget = st.slider("💰 總預算 (萬)", 10, 150, 60)
    with col2:
        usage = st.selectbox("🎯 主要用途", [
            "極致省油代步", 
            "家庭舒適空間", 
            "業務通勤耐操", 
            "面子社交商務",
            "熱血操控樂趣",
            "新手練車 (高折舊)"
        ])
    with col3:
        brand = st.selectbox("🚗 品牌偏好", brand_options)

    # 按鈕與執行
    if st.button("🔍 啟動 AI 掃描 (尋找最大利潤空間)"):
        if status != "SUCCESS":
            st.error("⚠️ 資料庫讀取失敗")
            return

        with st.spinner("🤖 正在掃描全台拍場庫存... 去除重複車源... 計算 TCO..."):
            time.sleep(0.8) 
            
            results = recommend_cars(df, budget, usage, brand)
            
            if not results.empty:
                st.success(f"✅ 掃描完成！鎖定 **{len(results)} 台** 最佳投資標的。")
                
                for i, (index, row) in enumerate(results.iterrows()):
                    car_name = row['車款名稱']
                    market_p = row['預估市價']
                    cost_p = row['成本底價']
                    savings = row['潛在省錢']
                    
                    with st.container():
                        st.markdown(f"""<div class='card-box'>""", unsafe_allow_html=True)
                        
                        # Title
                        c_title, c_badge = st.columns([3, 1])
                        with c_title:
                            st.subheader(f"🏆 標的 #{i+1}: {car_name}")
                        with c_badge:
                            st.markdown(f"<div style='text-align:right; color:#d32f2f; font-weight:bold; border: 2px solid #d32f2f; padding:5px; border-radius:5px;'>潛在獲利 {int(savings/10000)} 萬</div>", unsafe_allow_html=True)
                        
                        # Metrics
                        m1, m2, m3 = st.columns(3)
                        m1.metric("市場行情", f"{int(market_p/10000)} 萬")
                        m2.metric("拍場底價", f"{int(cost_p/10000)} 萬", delta="Cost", delta_color="inverse")
                        m3.metric("Arbitrage", f"{int(savings/10000)} 萬", delta="Profit", delta_color="normal")
                        
                        # AI Advice
                        if api_key:
                            advice = get_ai_advice(api_key, car_name, cost_p, market_p, savings)
                            st.markdown(f"<div style='background:#f1f8e9; padding:15px; border-left:5px solid #558b2f; border-radius:5px; color:#33691e;'><b>🤖 AI 投資顧問 (Elon Musk)：</b><br>{advice}</div>", unsafe_allow_html=True)
                        
                        # CTA
                        st.markdown("---")
                        b1, b2 = st.columns([4, 1])
                        with b1:
                            st.caption(f"📍 建議行動：立即鎖定 | TCO 評級：優良")
                        with b2:
                            st.markdown(f"[📲 聯絡 Brian 代標](https://line.me/ti/p/你的ID)", unsafe_allow_html=True) 
                        
                        st.markdown("</div>", unsafe_allow_html=True)

            else:
                st.warning("⚠️ 此預算下無符合的高利潤車款，請嘗試調整條件。")

if __name__ == "__main__":
    main()
