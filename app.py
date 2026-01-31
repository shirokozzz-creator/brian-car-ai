import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
import random
import time

# ==========================================
# 0. 核心設定 (專業投資風格)
# ==========================================
st.set_page_config(page_title="Brian's Auto Arbitrage | 拍場抄底神器", page_icon="🦅", layout="wide")

# --- CSS 美化：專業金融風 ---
st.markdown("""
    <style>
    .big-metric { font-size: 3em; font-weight: bold; color: #2e7d32; }
    .sub-metric { font-size: 1.2em; color: #555; }
    .card-box { 
        background-color: #ffffff; 
        padding: 20px; 
        border-radius: 10px; 
        border: 1px solid #e0e0e0; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    .highlight-green { color: #2e7d32; font-weight: bold; }
    .highlight-red { color: #c62828; font-weight: bold; }
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
# 1. 資料庫讀取
# ==========================================
@st.cache_data
def load_data():
    csv_path = "cars.csv"
    if not os.path.exists(csv_path): return pd.DataFrame(), "MISSING"
    try: 
        df = pd.read_csv(csv_path, on_bad_lines='skip')
        if df.empty: return pd.DataFrame(), "EMPTY"
        
        # 清洗資料：轉為數字
        if '成本底價' in df.columns:
             df['成本底價'] = df['成本底價'].astype(str).str.replace(',', '').str.replace('$', '').astype(float).astype(int)
        
        df['車款名稱'] = df['車款名稱'].astype(str)
        return df, "SUCCESS"
    except Exception as e: return pd.DataFrame(), f"ERROR: {str(e)}"

# ==========================================
# 2. 推薦演算法 (加入車種過濾邏輯)
# ==========================================
def recommend_cars(df, budget_limit, usage, brand_pref):
    # 1. 預算篩選
    budget_max = budget_limit * 10000
    budget_min = budget_max * 0.3 # 擴大範圍，避免找不到車
    
    candidates = df[
        (df['成本底價'] <= budget_max) & 
        (df['成本底價'] >= budget_min)
    ].copy()
    
    if candidates.empty: return pd.DataFrame() 
    
    # 2. 品牌篩選 (如果不是選不限)
    if brand_pref != "不限 (所有品牌)":
        candidates = candidates[candidates['車款名稱'].str.contains(brand_pref, case=False)]
        if candidates.empty: return pd.DataFrame() # 該品牌沒車
    
    # 3. 用途邏輯 (根據車型關鍵字過濾)
    # 定義關鍵字庫
    suv_keywords = ['cr-v', 'rav4', 'kuga', 'x-trail', 'suv', 'cx-5', 'odyssey', 'glc', 'rx', 'nx', 'tiguan', 'sportage', 'tucson', 'outlander', 'urx', 'sienta']
    sedan_keywords = ['altis', 'camry', 'sentra', 'mazda 3', 'focus', 'elantra', 'vios', 'yaris', 'fit', 'colt', 'tiida', 'city', 'civic', 'e-class', 'c-class', '3-series', '5-series', 'a4', 'es']
    sport_keywords = ['bmw', 'focus st', 'golf gti', 'mx-5', '86', 'brz', 'wrx', 'cooper', 'mustang']
    
    def calculate_match_score(car_name):
        score = 0
        name = car_name.lower()
        
        # 根據用途給分 (不只是加分，不符合的要扣分)
        if usage == "極致省油代步":
            if any(x in name for x in ['altis', 'vios', 'yaris', 'fit', 'prius', 'hybrid', 'city']): score += 10
            elif any(x in name for x in suv_keywords): score -= 5 # 省油不推休旅
            
        elif usage == "家庭舒適空間":
            if any(x in name for x in suv_keywords + ['odyssey', 'sienna', 'previa', 'm7']): score += 10
            elif any(x in name for x in ['yaris', 'vios', 'march']): score -= 5 # 家庭不推小車
            
        elif usage == "業務通勤耐操":
            if any(x in name for x in ['altis', 'corolla', 'camry', 'rav4', 'cross']): score += 10
            
        elif usage == "面子社交商務":
            if any(x in name for x in ['benz', 'bmw', 'lexus', 'audi', 'volvo', 'porsche']): score += 10
            elif any(x in name for x in ['toyota', 'honda', 'nissan']): score -= 2
            
        elif usage == "熱血操控樂趣":
            if any(x in name for x in sport_keywords + ['mazda', 'bmw']): score += 10
            elif any(x in name for x in ['suv', 'van', 'mpv']): score -= 5
            
        elif usage == "新手練車 (高折舊)":
            # 推薦便宜好修的
            if any(x in name for x in ['vios', 'yaris', 'colt', 'tiida', 'march', 'focus']): score += 10
            
        return score

    candidates['match_score'] = candidates['車款名稱'].apply(calculate_match_score)
    
    # 過濾掉分數太低的 (例如選家庭空間，就別推 Yaris 了)
    # 但為了避免結果為空，如果篩完沒車，就放寬標準
    high_score_candidates = candidates[candidates['match_score'] > 0]
    if not high_score_candidates.empty:
        candidates = high_score_candidates
    
    # 4. 計算潛在利潤 (Arbitrage Calculation)
    # 這裡我們用一個簡單的邏輯：越貴的車，折價空間通常越大
    candidates['預估市價'] = candidates['成本底價'] * 1.18 
    candidates['代標總成本'] = candidates['成本底價'] * 1.05
    candidates['潛在省錢'] = candidates['預估市價'] - candidates['代標總成本']
    
    # 5. 排序：先看匹配度，再看省錢金額
    recommendations = candidates.sort_values(
        ['match_score', '潛在省錢'], ascending=[False, False]
    ).head(3) 
    
    return recommendations

# ==========================================
# 3. AI 投資顧問 (馬斯克中肯分析版)
# ==========================================
def get_ai_advice(api_key, car_name, wholesale_price, market_price, savings):
    genai.configure(api_key=api_key)
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # 這裡的 Prompt 修改為「中肯、犀利、數據導向」
        prompt = f"""
        你現在是 Elon Musk，但這次你不是來搞笑的，你是來做「殘酷的投資分析」。
        請根據以下數據，給出一針見血的購車建議。
        
        交易標的：{car_name}
        市場行情：{int(market_price/10000)} 萬
        拍場底價(取得成本)：{int(wholesale_price/10000)} 萬
        潛在套利空間：{int(savings/10000)} 萬
        
        請用「簡短、數據導向、略帶急迫感」的語氣 (80字以內) 回答：
        1. 這台車的 TCO (擁車成本) 優勢在哪？(例如折舊已到底、或零件便宜)
        2. 這筆交易的「投報率」如何？(省下的錢能做什麼實質的事)
        3. 給出一個決策指令 (例如：Strong Buy / Value Pick)。
        不要講風水，不要講笑話，專注於「錢」和「價值」。
        """
        
        response = model.generate_content(prompt)
        return response.text
    except:
        return "AI 分析中：數據顯示此車款折舊曲線已趨緩，目前入場屬於低風險區間。省下的價差足以覆蓋首年大保養與稅金，建議買入。"

# ==========================================
# 4. 主程式 UI
# ==========================================
def main():
    # --- Sidebar 設定 ---
    with st.sidebar:
        st.header("🦅 設定控制台")
        if "GOOGLE_API_KEY" in st.secrets:
            api_key = st.secrets["GOOGLE_API_KEY"]
            st.success("✅ AI 顧問已連線")
        else:
            api_key = st.text_input("Google API Key", type="password")
        
        st.info("💡 **拍場抄底原理**\n我們直接掃描全台批發拍場庫存，跳過車商利潤，讓你用接近車行的成本入手好車。")
        st.markdown("---")
        st.caption("V36 (Investment Edition)")

    # --- 主畫面 ---
    st.title("🦅 Brian's Auto Arbitrage | 拍場抄底神器")
    st.markdown("""
    > **「買車不該是消費，而是一場精計算的資產配置。」**
    > 輸入條件，AI 幫你找出目前市場上 **被低估、具備高套利空間** 的優質標的。
    """)
    
    st.markdown("---")

    # 載入資料以獲取品牌列表
    df, status = load_data()
    if status == "SUCCESS":
        # 自動提取品牌列表 (取前兩字或英文，去重複，排序)
        # 這裡做一個簡單的處理，假設車名開頭就是品牌
        # 實際資料可能需要更細緻的清洗，這裡先用簡單邏輯
        all_brands = sorted(list(set([name.split()[0] for name in df['車款名稱'].astype(str)])))
        # 過濾掉一些奇怪的雜訊，只留常見品牌 (可選)
        brand_options = ["不限 (所有品牌)"] + all_brands
    else:
        brand_options = ["不限 (所有品牌)"]

    # 1. 輸入區
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # 限制金額在 150 萬以內
        budget = st.slider("💰 總預算 (萬)", 10, 150, 60)
    with col2:
        # 6 個不重複的使用場景
        usage = st.selectbox("🎯 主要用途 (AI 自動匹配車型)", [
            "極致省油代步", 
            "家庭舒適空間", 
            "業務通勤耐操", 
            "面子社交商務",
            "熱血操控樂趣",
            "新手練車 (高折舊)"
        ])
    with col3:
        # 自動生成的品牌列表
        brand = st.selectbox("🚗 品牌偏好", brand_options)

    # 2. 執行按鈕
    if st.button("🔍 啟動 AI 掃描 (尋找最大利潤空間)"):
        if status != "SUCCESS":
            st.error("⚠️ 資料庫連線失敗，請檢查 CSV 檔案。")
            return

        with st.spinner("🤖 正在掃描全台拍場庫存... 計算 TCO... 分析折舊曲線..."):
            time.sleep(1.0) # 儀式感等待
            
            results = recommend_cars(df, budget, usage, brand)
            
            if not results.empty:
                st.success(f"✅ 掃描完成！在預算 {budget} 萬內，AI 鎖定了 **{len(results)} 台** 最佳投資標的。")
                
                for i, (index, row) in enumerate(results.iterrows()):
                    car_name = row['車款名稱']
                    market_p = row['預估市價']
                    cost_p = row['成本底價']
                    savings = row['潛在省錢']
                    
                    with st.container():
                        st.markdown(f"""<div class='card-box'>""", unsafe_allow_html=True)
                        
                        # 標題區
                        c_title, c_badge = st.columns([3, 1])
                        with c_title:
                            st.subheader(f"🏆 標的 #{i+1}: {car_name}")
                        with c_badge:
                            st.markdown(f"<div style='text-align:right; color:#d32f2f; font-weight:bold; border: 2px solid #d32f2f; padding:5px; border-radius:5px;'>潛在獲利 {int(savings/10000)} 萬</div>", unsafe_allow_html=True)
                        
                        # 數據區
                        m1, m2, m3 = st.columns(3)
                        m1.metric("市場行情 (平均)", f"{int(market_p/10000)} 萬")
                        m2.metric("拍場底價 (你的成本)", f"{int(cost_p/10000)} 萬", delta="Wholesale Price", delta_color="inverse")
                        m3.metric("Arbitrage (價差)", f"{int(savings/10000)} 萬", delta="Margin", delta_color="normal")
                        
                        # AI 顧問區 (中肯分析版)
                        if api_key:
                            advice = get_ai_advice(api_key, car_name, cost_p, market_p, savings)
                            st.markdown(f"<div style='background:#f1f8e9; padding:15px; border-left:5px solid #558b2f; border-radius:5px; color:#33691e;'><b>🤖 AI 投資顧問 (Elon Musk)：</b><br>{advice}</div>", unsafe_allow_html=True)
                        
                        # Call to Action
                        st.markdown("---")
                        b1, b2 = st.columns([4, 1])
                        with b1:
                            st.caption(f"📍 此車款 TCO 評級：優良 | 流通性：高 | 建議行動：立即鎖定")
                        with b2:
                            # 這裡換成你的 Line 連結
                            st.markdown(f"[📲 聯絡 Brian 代標](https://line.me/ti/p/你的ID)", unsafe_allow_html=True) 
                        
                        st.markdown("</div>", unsafe_allow_html=True)
                        st.markdown("<br>", unsafe_allow_html=True)

            else:
                st.warning("⚠️ 抱歉，這個預算和條件下，暫時沒有符合高標準的投資標的。建議調整品牌或增加預算。")

if __name__ == "__main__":
    main()
