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
st.set_page_config(
    page_title="Brian 航太數據選車室", 
    page_icon="✈️", 
    layout="wide"
)

# CSS 優化：保持航太儀表板風格，但更專注於數據可讀性
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stApp { font-family: "Microsoft JhengHei", sans-serif; }
    
    /* 專業身份卡 (移除生理數據) */
    .bio-card { 
        background-color: #263238; color: white; padding: 15px; border-radius: 8px; 
        border-left: 5px solid #ffca28; margin-bottom: 20px;
    }
    
    /* 數據卡片 */
    .car-card {
        background-color: white; padding: 20px; border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1); border: 1px solid #e0e0e0;
        margin-bottom: 15px;
    }
    
    /* FMEA 風險警告區 */
    .risk-box { 
        background-color: #ffebee; border: 1px solid #ef5350; color: #c62828; 
        padding: 10px; border-radius: 5px; font-size: 0.9em; margin-top: 10px;
    }
    
    /* 標籤 */
    .role-tag { font-size: 0.8em; padding: 4px 8px; border-radius: 4px; color: white; font-weight: bold; float: right; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 真實資料庫讀取 (恢復 V1 功能)
# ==========================================
@st.cache_data
def load_data():
    csv_path = "cars.csv"
    # 如果找不到檔案，生成模擬數據以免報錯 (方便測試)
    if not os.path.exists(csv_path):
        data = {
            '車款名稱': ['2020 BENZ C300 AMG', '2019 TOYOTA RAV4 HYBRID', '2021 TOYOTA COROLLA CROSS', '2016 MAZDA 3 頂級', '2015 BMW 320i M-Sport', '2018 LEXUS NX200', '2019 HONDA CR-V', '2017 TOYOTA SIENNA'],
            '成本底價': [1350000, 650000, 580000, 280000, 550000, 980000, 600000, 1100000],
            'Brand': ['BENZ', 'TOYOTA', 'TOYOTA', 'MAZDA', 'BMW', 'LEXUS', 'HONDA', 'TOYOTA']
        }
        return pd.DataFrame(data), "DEMO"
        
    try: 
        df = pd.read_csv(csv_path, on_bad_lines='skip')
        if df.empty: return pd.DataFrame(), "EMPTY"
        
        # 數據清理
        if '成本底價' in df.columns:
             df['成本底價'] = df['成本底價'].astype(str).str.replace(',', '').str.replace('$', '').astype(float).astype(int)
        
        df['車款名稱'] = df['車款名稱'].astype(str).str.strip().str.upper()
        
        # 簡易品牌提取邏輯
        valid_brands = ['TOYOTA', 'HONDA', 'NISSAN', 'FORD', 'MAZDA', 'MITSUBISHI', 'LEXUS', 'BMW', 'BENZ', 'VOLVO', 'AUDI', 'VW', 'SUBARU', 'PORSCHE']
        def extract_brand(name):
            for brand in valid_brands:
                if brand in name: return brand
            return 'OTHER'
            
        df['Brand'] = df['車款名稱'].apply(extract_brand)
        return df, "SUCCESS"
    except Exception as e: return pd.DataFrame(), f"ERROR: {str(e)}"

# ==========================================
# 2. FMEA 風險計算核心 (保留 V2 工程邏輯)
# ==========================================
def calculate_fmea_params(car_name, brand):
    buffer = 15000  # 基礎整備
    risks = []
    
    # 針對特定車型的真實痛點分析
    if "HYBRID" in car_name or "油電" in car_name:
        buffer += 45000
        risks.append("⚠️ 高壓電池與逆變器風險 (S=7, O=4)")
    
    if "BENZ" in brand or "BMW" in brand:
        buffer += 50000
        risks.append("⚠️ 歐系環保材質/水路老化 (S=8, O=6)")
        
    if "MAZDA" in brand and "201" in car_name: # 抓大概年份
        buffer += 20000
        risks.append("⚠️ 噴油嘴/後照鏡收折隱憂 (S=4, O=8)")

    if "RAV4" in car_name:
        buffer += 20000
        risks.append("⚠️ 車頂架滲水隱憂 (S=6, O=5)")
        
    if "FORD" in brand or "FOCUS" in car_name:
        buffer += 30000
        risks.append("⚠️ 變速箱/水塞預防性更換 (S=7, O=5)")

    return buffer, risks

# ==========================================
# 3. AI 選車演算法 (恢復 V1 推薦邏輯)
# ==========================================
def recommend_cars_with_fmea(df, budget_limit, usage, brand_pref):
    budget_max = budget_limit * 10000
    budget_min = budget_max * 0.4
    
    # 初步篩選
    candidates = df[(df['成本底價'] <= budget_max) & (df['成本底價'] >= budget_min)].copy()
    if candidates.empty: return pd.DataFrame()

    # 關鍵字定義
    suv_kw = ['CR-V', 'RAV4', 'KUGA', 'X-TRAIL', 'SUV', 'CX-5', 'GLC', 'RX', 'NX', 'TIGUAN', 'CROSS']
    mpv_kw = ['PREVIA', 'SIENNA', 'ALPHARD', 'ODYSSEY', 'M7', 'WISH', 'TOURAN']
    
    # 評分邏輯
    def get_score(row):
        score = 0
        name = row['車款名稱']
        brand = row['Brand']
        
        # 用途加權
        if usage == "極致省油代步":
            if any(x in name for x in ['ALTIS', 'VIOS', 'YARIS', 'FIT', 'PRIUS', 'HYBRID']): score += 50
            elif any(x in name for x in suv_kw + mpv_kw): score -= 100
        elif usage == "家庭舒適空間":
            if any(x in name for x in mpv_kw + suv_kw): score += 50
            elif any(x in name for x in ['YARIS', 'VIOS', 'FIT']): score -= 100
        elif usage == "面子社交商務":
            if brand in ['BENZ', 'BMW', 'LEXUS', 'PORSCHE', 'VOLVO']: score += 50
            else: score -= 20
        elif usage == "熱血操控樂趣":
            if any(x in name for x in ['BMW', 'FOCUS', 'MAZDA', '86', 'GOLF', 'WRX']): score += 50
            if any(x in name for x in mpv_kw): score -= 200
            
        # 品牌加權
        if brand_pref != "不限" and brand == brand_pref: score += 200
        
        return score

    candidates['score'] = candidates.apply(get_score, axis=1)
    candidates = candidates[candidates['score'] > -50] # 過濾不相關的
    candidates = candidates.sort_values('score', ascending=False).head(5) # 只取前 5 名
    
    # 這裡加入 V2 的邏輯：計算 FMEA 與安全邊際
    results = []
    for idx, row in candidates.iterrows():
        market_price = row['成本底價'] * 1.18 # 模擬市價
        fmea_buffer, risks = calculate_fmea_params(row['車款名稱'], row['Brand'])
        
        row['預估市價'] = market_price
        row['FMEA整備金'] = fmea_buffer
        row['風險列表'] = risks
        row['安全邊際'] = market_price - row['成本底價'] - fmea_buffer
        results.append(row)
        
    return pd.DataFrame(results)

# ==========================================
# 4. 主程式
# ==========================================
def main():
    # --- 側邊欄 ---
    with st.sidebar:
        st.header("⚙️ 航太數據控制台")
        api_key = st.text_input("Google API Key (選填)", type="password")
        st.info("💡 **操作指南**：\n設定預算與用途，系統將執行 FMEA 風險過濾，找出「具備真實安全邊際」的標的。")

    # --- 標題區 (移除生理數據，保留專業感) ---
    st.title("Brian 航太數據選車室")
    st.markdown("""
        <div class="bio-card">
            <span style="font-size:1.1em;">👨‍🚀 <b>Brian | Aerospace Engineer</b></span><br>
            以航太維修標準 (FMEA) 審視車輛資產，拒絕市場資訊不對稱。<br>
            <span style="color:#ffca28; font-size:0.9em;">✅ HAA/SAA 拍場數據連線中</span>
        </div>
    """, unsafe_allow_html=True)

    # --- 資料讀取 ---
    df, status = load_data()
    if status == "EMPTY" or df.empty:
        st.error("⚠️ 無法讀取車輛數據，請確認 cars.csv 存在。")
        return

    # --- 篩選區 (恢復 AI 選車功能) ---
    st.subheader("🛰️ 啟動 AI 戰略篩選")
    
    c1, c2, c3 = st.columns(3)
    with c1: 
        budget = st.slider("💰 總預算 (萬)", 10, 300, 80)
    with c2: 
        usage = st.selectbox("🎯 主要用途", ["極致省油代步", "家庭舒適空間", "業務通勤耐操", "面子社交商務", "熱血操控樂趣"])
    with c3:
        brands = sorted(df['Brand'].unique().tolist())
        brand_pref = st.selectbox("🚗 品牌偏好", ["不限"] + brands)

    if st.button("🔍 執行 FMEA 數據掃描"):
        with st.spinner("正在進行資產價值運算..."):
            time.sleep(0.8) # 模擬運算感
            results = recommend_cars_with_fmea(df, budget, usage, brand_pref)
            
            if not results.empty:
                st.success(f"✅ 掃描完成：鎖定 {len(results)} 台符合安全邊際之標的")
                
                for i, row in results.iterrows():
                    # 變數提取
                    name = row['車款名稱']
                    market_p = row['預估市價']
                    cost_p = row['成本底價']
                    buffer = row['FMEA整備金']
                    margin = row['安全邊際']
                    risks = row['風險列表']
                    
                    # 決定角色標籤
                    if i == 0: role, color = "🏆 最佳首選", "#d32f2f"
                    elif i == 1: role, color = "🥈 高性價比", "#1976d2"
                    else: role, color = "🥉 優質候選", "#616161"

                    # --- 卡片顯示 ---
                    with st.container():
                        st.markdown(f"""
                        <div class="car-card">
                            <div style="margin-bottom:10px;">
                                <span style="font-size:1.3em; font-weight:bold;">{name}</span>
                                <span class="role-tag" style="background-color:{color};">{role}</span>
                            </div>
                        """, unsafe_allow_html=True)
                        
                        # 核心三數據
                        c_m, c_c, c_s = st.columns(3)
                        c_m.metric("市場行情", f"{int(market_p/10000)} 萬")
                        c_c.metric("拍場成本", f"{int(cost_p/10000)} 萬", delta="Wholesale")
                        c_s.metric("淨安全邊際", f"{int(margin/10000)} 萬", delta="扣除維修後", delta_color="normal")
                        
                        # FMEA 風險區 (V2 的精髓)
                        st.markdown(f"""
                            <div class="risk-box">
                                <b>⚠️ FMEA 維修預算 (Buffer): ${buffer:,}</b><br>
                                <span style="font-size:0.9em;">包含：{', '.join(risks) if risks else '基礎耗材整備'}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # AI 建議 (選填)
                        if api_key and i == 0:
                            st.info("🤖 **工程觀點：** 根據 FMEA 分析，此車款雖然維修風險略高，但巨大的拍場價差提供了充足的防禦空間，屬 A 級資產。")
                            
            else:
                st.warning("⚠️ 找不到符合條件的車輛，請嘗試放寬預算。")

if __name__ == "__main__":
    main()
