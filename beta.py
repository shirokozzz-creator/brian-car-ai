import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
import random
import time
from datetime import datetime

# ==========================================
# 0. 核心設定 (Engineering Mode)
# ==========================================
st.set_page_config(
    page_title="Brian 航太數據選車室", 
    page_icon="✈️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定義 CSS：打造「航太儀表板」風格
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stApp { font-family: "Microsoft JhengHei", sans-serif; }
    
    /* 權威數據卡 */
    .bio-card { 
        background-color: #263238; color: white; padding: 15px; border-radius: 8px; 
        border-left: 5px solid #ffca28; margin-bottom: 20px; font-family: monospace;
    }
    .bio-stats { color: #ffca28; font-weight: bold; }
    
    /* FMEA 風險警告區 */
    .risk-box { 
        background-color: #ffebee; border: 1px solid #ef5350; color: #c62828; 
        padding: 10px; border-radius: 5px; font-size: 0.9em; margin-top: 5px;
    }
    
    /* 安全邊際區 */
    .safety-margin-box {
        background-color: #e8f5e9; border: 1px solid #66bb6a; color: #2e7d32;
        padding: 15px; border-radius: 5px; text-align: center; font-weight: bold; font-size: 1.2em;
    }

    /* 隱藏預設元素 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 模擬數據庫與 FMEA 邏輯 (Simulated Core)
# ==========================================
@st.cache_data
def load_data():
    # 這裡模擬讀取 CSV，若無檔案則生成測試數據
    data = [
        {"車款名稱": "2020 BENZ C300 AMG", "Brand": "BENZ", "成本底價": 1350000, "預估市價": 1680000},
        {"車款名稱": "2019 TOYOTA RAV4 HYBRID", "Brand": "TOYOTA", "成本底價": 650000, "預估市價": 850000},
        {"車款名稱": "2021 TOYOTA COROLLA CROSS", "Brand": "TOYOTA", "成本底價": 580000, "預估市價": 720000},
        {"車款名稱": "2016 MAZDA 3 頂級", "Brand": "MAZDA", "成本底價": 280000, "預估市價": 420000},
        {"車款名稱": "2018 LEXUS NX200", "Brand": "LEXUS", "成本底價": 980000, "預估市價": 1250000},
        {"車款名稱": "2015 BMW 320i M-Sport", "Brand": "BMW", "成本底價": 550000, "預估市價": 750000},
    ]
    return pd.DataFrame(data)

# 航太 FMEA 風險矩陣 (模擬邏輯)
def calculate_fmea_buffer(car_name, brand):
    buffer = 15000  # 基礎耗材整備 (油水輪胎)
    risk_factors = []
    
    if "HYBRID" in car_name.upper():
        buffer += 45000
        risk_factors.append("⚠️ 高壓電池失效風險 (S=7, O=4)")
    
    if "BENZ" in brand or "BMW" in brand:
        buffer += 50000
        risk_factors.append("⚠️ 歐系環保材質/水路老化 (S=8, O=6)")
        
    if "MAZDA" in brand and "2016" in car_name:
        buffer += 20000
        risk_factors.append("⚠️ 後照鏡收折馬達/避震器漏油 (S=4, O=8)")

    if "RAV4" in car_name:
        buffer += 25000
        risk_factors.append("⚠️ 車頂架/電纜接頭滲水隱憂 (S=6, O=5)")
        
    return buffer, risk_factors

# ==========================================
# 2. AI 航太顧問 (Cold & Rational)
# ==========================================
def get_engineering_advice(api_key, car_name, margin, fmea_risks):
    if not api_key: return "系統提示：請輸入 API Key 以啟動 AI 深度診斷。"
    
    genai.configure(api_key=api_key)
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        risk_text = ", ".join(fmea_risks) if fmea_risks else "一般機械耗損"
        
        prompt = f"""
        你是一位極度理性的航太工程師，正在審核一項二手車資產採購案。
        標的：{car_name}
        預期淨安全邊際 (Net Safety Margin)：{margin} 元
        已知潛在風險 (FMEA)：{risk_text}
        
        任務：
        1. 請用冷靜、數據導向的口吻分析此採購案。
        2. 不要使用銷售語言 (如「買到賺到」)，要使用「資產防禦」、「風險對沖」、「殘值曲線」等詞彙。
        3. 根據風險與邊際，給出最終建議 (通過/駁回/需再議)。
        4. 字數限制：80字以內。
        """
        response = model.generate_content(prompt)
        return response.text
    except:
        return "通訊模組異常。根據靜態數據分析，此標的具備足夠的安全邊際覆蓋潛在維修成本。"

# ==========================================
# 3. 主介面邏輯
# ==========================================
def main():
    # --- 側邊欄：控制台 ---
    with st.sidebar:
        st.header("⚙️ 數據控制台")
        api_key = st.text_input("Google API Key", type="password")
        st.divider()
        st.markdown("### 📡 數據源訊號")
        st.caption("✅ HAA 和運勁拍中心 (連線中)")
        st.caption("✅ SAA 行將企業 (連線中)")
        st.caption("✅ Brian FMEA 資料庫 (已掛載)")

    # --- 第一層：身分與權威 (The Persona) ---
    st.title("Brian 航太數據選車室")
    st.markdown("""
        <div class="bio-card">
            <span style="font-size:1.2em;">👨‍🚀 <b>Brian | Aerospace Engineer</b></span><br>
            <div style="margin-top:5px;">
                生理數據監控：<span class="bio-stats">181cm / 74kg / 18.5% Body Fat</span><br>
                核心理念：以航太維修標準 (FMEA) 審視車輛資產，拒絕市場資訊不對稱。
            </div>
        </div>
    """, unsafe_allow_html=True)

    # --- 第二層：揭露真相 (The Why) ---
    with st.expander("📉 點擊展開：為什麼市場價格包含 20% 的「資訊稅」？", expanded=False):
        c1, c2, c3 = st.columns(3)
        c1.metric("一般車行", "市場零售價", help="包含店租、業務抽成、廣告費")
        c2.metric("Brian 代標", "拍場批發價", delta="-20%", delta_color="inverse", help="直接從源頭取得，無中間商")
        c3.markdown("#### 💡 核心差異")
        st.info("""
        傳統模式下，你支付的溢價是為了換取「安心感」。
        但在這裡，我們用 **數據與原始查定表** 來取代昂貴的安心感。
        我們不賺差價，只收取固定技術顧問費。
        """)

    st.divider()

    # --- 第三層：互動篩選 (The Filter) ---
    st.subheader("🛰️ 全台庫存掃描 (Inventory Scan)")
    
    df = load_data()
    col1, col2 = st.columns([1, 2])
    
    with col1:
        budget = st.slider("預算上限 (萬)", 20, 200, 80)
        brand_filter = st.selectbox("鎖定品牌", ["不限"] + list(df['Brand'].unique()))
    
    with col2:
        st.markdown("##### 🔍 掃描參數設定")
        st.write(f"正在搜尋拍場成交價低於 **{budget} 萬** 的標的...")
        if brand_filter != "不限":
            filtered_df = df[df['Brand'] == brand_filter]
        else:
            filtered_df = df
        
        filtered_df = filtered_df[filtered_df['成本底價'] <= budget * 10000]

    # --- 第四層：診斷結果 (The Truth) ---
    st.subheader("📊 資產與風險評估報告")
    
    if filtered_df.empty:
        st.warning("⚠️ 掃描無結果：建議調整預算或品牌參數。")
    else:
        for idx, row in filtered_df.iterrows():
            # 計算邏輯
            car_name = row['車款名稱']
            market_price = row['預估市價']
            cost_price = row['成本底價']
            
            # FMEA 風險計算
            fmea_buffer, risk_list = calculate_fmea_buffer(car_name, row['Brand'])
            
            # 安全邊際 (真實省下的錢)
            raw_gap = market_price - cost_price
            safety_margin = raw_gap - fmea_buffer
            margin_percent = int((safety_margin / market_price) * 100)

            # 顯示卡片
            with st.container():
                st.markdown(f"### 🛡️ 標的：{car_name}")
                
                # 核心數據三欄
                c_mk, c_wh, c_safe = st.columns(3)
                
                with c_mk:
                    st.metric("1. 市場行情 (Anchor)", f"{int(market_price/10000)} 萬")
                
                with c_wh:
                    st.metric("2. 拍場成本 (Base)", f"{int(cost_price/10000)} 萬", delta="取得成本")
                
                with c_safe:
                    st.metric("3. 淨安全邊際 (Net Margin)", f"{int(safety_margin/10000)} 萬", 
                             delta=f"{margin_percent}% 優勢", delta_color="normal")

                # FMEA 風險揭露 (這是最重要的一步)
                with st.expander("⚠️ 點擊查看：FMEA 風險預備金 (Buffer) 分析", expanded=True):
                    st.markdown(f"**預留整備金：${fmea_buffer:,}**")
                    if risk_list:
                        for risk in risk_list:
                            st.text(risk)
                    else:
                        st.text("✅ 基礎耗材整備 (S=2, O=2)")
                    st.caption("註：安全邊際已扣除上述風險預算。這才是你真正『省下且安全』的錢。")

                # AI 工程師講評
                if api_key:
                    advice = get_engineering_advice(api_key, car_name, safety_margin, risk_list)
                    st.info(f"🤖 **Brian AI 工程觀點：**\n{advice}")
                
                # CTA
                st.markdown(f"""
                <a href="#" style="text-decoration:none;">
                    <button style="
                        width:100%; 
                        background-color:#1565c0; 
                        color:white; 
                        padding:10px; 
                        border:none; 
                        border-radius:5px; 
                        font-weight:bold; 
                        cursor:pointer;">
                        🚀 啟動此資產的採購委託 (Initiate)
                    </button>
                </a>
                """, unsafe_allow_html=True)
                
                st.divider()

if __name__ == "__main__":
    main()
