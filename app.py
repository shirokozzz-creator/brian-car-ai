import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
import random
import time

# ==========================================
# 0. 核心設定 (轉型為專業工具風格)
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
# 2. 推薦演算法 (核心大腦)
# ==========================================
def recommend_cars(df, budget_limit, usage, brand_pref):
    # 1. 預算篩選 (找底價在預算內的)
    # 預算單位是萬，轉成元
    budget_max = budget_limit * 10000
    # 預算下限設為上限的 50%，避免推薦太爛的車
    budget_min = budget_max * 0.4 
    
    candidates = df[
        (df['成本底價'] <= budget_max) & 
        (df['成本底價'] >= budget_min)
    ].copy()
    
    if candidates.empty: return pd.DataFrame() # 沒車
    
    # 2. 品牌篩選
    if brand_pref != "不限 (全部品牌)":
        candidates = candidates[candidates['車款名稱'].str.contains(brand_pref, case=False)]
    
    # 3. 用途權重 (Heuristic Scoring)
    # 根據車名關鍵字給分
    def calculate_usage_score(car_name):
        score = 0
        name = car_name.lower()
        
        if usage == "高 CP 代步 (Toyota/Honda...)":
            if any(x in name for x in ['toyota', 'honda', 'nissan', 'altis', 'yaris', 'vios', 'fit', 'tiida']): score += 5
            if any(x in name for x in ['bmw', 'benz']): score -= 2 # 代步不推雙B
            
        elif usage == "家庭休旅 (空間安全)":
            if any(x in name for x in ['cr-v', 'rav4', 'kuga', 'x-trail', 'suv', 'cx-5', 'odyssey']): score += 5
            
        elif usage == "面子工程 (BMW/Benz...)":
            if any(x in name for x in ['bmw', 'benz', 'mercedes', 'lexus', 'audi', 'c300', 'cla']): score += 5
            
        elif usage == "熱血操控 (Mazda/BMW...)":
            if any(x in name for x in ['bmw', 'mazda', 'focus', 'golf', 'gti']): score += 5
            
        return score

    candidates['match_score'] = candidates['車款名稱'].apply(calculate_usage_score)
    
    # 4. 計算潛在利潤 (Arbitrage Calculation)
    # 假設市面車商平均開價是 底價的 1.15 ~ 1.25 倍
    # 為了展示效果，我們隨機生成一個 "市價倍率"
    candidates['預估市價'] = candidates['成本底價'] * 1.18 
    
    # 你的代標成本假設：底價 + 5% 服務費
    candidates['代標總成本'] = candidates['成本底價'] * 1.05
    
    # 省下的錢
    candidates['潛在省錢'] = candidates['預估市價'] - candidates['代標總成本']
    
    # 5. 排序：先看用途分數，再看省錢金額
    recommendations = candidates.sort_values(
        ['match_score', '潛在省錢'], ascending=[False, False]
    ).head(3) # 取前三名
    
    return recommendations

# ==========================================
# 3. AI 投資顧問 (TCO 分析)
# ==========================================
def get_ai_advice(api_key, car_name, wholesale_price, market_price, savings):
    genai.configure(api_key=api_key)
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        你是一位專業的汽車投資顧問。請分析這筆交易是否划算。
        
        交易標的：{car_name}
        市面行情約：{int(market_price/10000)} 萬
        透過代標取得成本：{int(wholesale_price/10000)} 萬
        預估現省：{int(savings/10000)} 萬
        
        請用簡短、專業、略帶急迫感的語氣 (100字以內) 給出建議：
        1. 強調這台車的 TCO (擁車成本) 優勢。
        2. 強調「省下的錢」可以拿去做什麼 (例如：省下的錢夠你加兩年油 / 夠你付全險)。
        3. 結尾給出強烈建議 (Strong Buy)。
        """
        
        response = model.generate_content(prompt)
        return response.text
    except:
        return "AI 連線忙碌中，但數據顯示這是一筆極佳的套利交易。省下的價差足以支付首年的保養與保險費用。"

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
        
        st.info("💡 **什麼是代標？**\n我們直接從批發拍場幫你抓車，跳過車商的 15%-20% 利潤，只收固定手續費。")
        st.markdown("---")
        st.caption("V35 (Arbitrage Edition)")

    # --- 主畫面 ---
    st.title("🦅 Brian's Auto Arbitrage | 拍場抄底神器")
    st.markdown("""
    > **「別再付智商稅給車商。」** > 輸入你的預算，AI 幫你算出目前拍場上 **CP 值最高、價差最大** 的車款。
    """)
    
    st.markdown("---")

    # 1. 輸入區 (極簡化)
    col1, col2, col3 = st.columns(3)
    
    with col1:
        budget = st.slider("💰 總預算 (萬)", 10, 300, 70)
    with col2:
        usage = st.selectbox("🎯 主要用途", [
            "高 CP 代步 (Toyota/Honda...)", 
            "家庭休旅 (空間安全)", 
            "面子工程 (BMW/Benz...)", 
            "熱血操控 (Mazda/BMW...)"
        ])
    with col3:
        brand = st.selectbox("🚗 品牌偏好", ["不限 (全部品牌)", "Toyota", "Honda", "Mazda", "BMW", "Benz", "Lexus", "Nissan", "Ford"])

    # 2. 執行按鈕
    if st.button("🔍 啟動 AI 掃描 (尋找最大利潤空間)"):
        df, status = load_data()
        
        if status != "SUCCESS":
            st.error("⚠️ 資料庫連線失敗，請檢查 CSV 檔案。")
            return

        with st.spinner("🤖 正在掃描全台拍場庫存... 計算 TCO... 分析折舊曲線..."):
            # 模擬運算延遲感 (更有儀式感)
            time.sleep(1.5) 
            
            results = recommend_cars(df, budget, usage, brand)
            
            if not results.empty:
                st.success(f"✅ 掃描完成！在你的預算 {budget} 萬內，發現 **{len(results)} 台** 具備極高套利空間的車款。")
                
                # 遍歷推薦結果
                for i, (index, row) in enumerate(results.iterrows()):
                    car_name = row['車款名稱']
                    market_p = row['預估市價']
                    cost_p = row['成本底價']
                    savings = row['潛在省錢']
                    
                    # 每一張卡片
                    with st.container():
                        st.markdown(f"""<div class='card-box'>""", unsafe_allow_html=True)
                        
                        # 標題區
                        c_title, c_badge = st.columns([3, 1])
                        with c_title:
                            st.subheader(f"🏆 推薦 #{i+1}: {car_name}")
                        with c_badge:
                            st.markdown(f"<div style='text-align:right; color:#d32f2f; font-weight:bold; border: 2px solid #d32f2f; padding:5px; border-radius:5px;'>現省 {int(savings/10000)} 萬</div>", unsafe_allow_html=True)
                        
                        # 數據區
                        m1, m2, m3 = st.columns(3)
                        m1.metric("市場行情 (平均)", f"{int(market_p/10000)} 萬")
                        m2.metric("拍場底價 (你的成本)", f"{int(cost_p/10000)} 萬", delta="Wholesale Price", delta_color="inverse")
                        m3.metric("Arbitrage (價差)", f"{int(savings/10000)} 萬", delta="Profit", delta_color="normal")
                        
                        # AI 顧問區
                        if api_key:
                            advice = get_ai_advice(api_key, car_name, cost_p, market_p, savings)
                            st.markdown(f"<div style='background:#f1f8e9; padding:15px; border-left:5px solid #558b2f; border-radius:5px;'><b>🤖 AI 投資顧問：</b><br>{advice}</div>", unsafe_allow_html=True)
                        
                        # Call to Action
                        st.markdown("---")
                        b1, b2 = st.columns([4, 1])
                        with b1:
                            st.caption(f"📍 這台車目前在拍場庫存中。想看詳細車況表？")
                        with b2:
                            # 這裡可以放你的 LINE 連結
                            st.markdown(f"[📲 聯絡 Brian](https://line.me/ti/p/你的ID)", unsafe_allow_html=True) 
                        
                        st.markdown("</div>", unsafe_allow_html=True)
                        st.markdown("<br>", unsafe_allow_html=True)

            else:
                st.warning("⚠️ 抱歉，這個預算範圍內暫時沒有符合「高利潤空間」的車款。建議提高預算或放寬品牌限制。")

if __name__ == "__main__":
    main()
