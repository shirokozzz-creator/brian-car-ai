import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageDraw, ImageFont
import pandas as pd
import os
import io
import textwrap
import json
import random
import time

# ==========================================
# 0. 核心設定
# ==========================================
st.set_page_config(page_title="Brian AI 戰情室 (V28-神隱版)", page_icon="🦅", layout="centered")

# --- 字型設定 ---
FONT_PATH_BOLD = "msjhbd.ttc" 
FONT_PATH_REG = "msjh.ttc"

try:
    title_font = ImageFont.truetype(FONT_PATH_BOLD, 40)
    subtitle_font = ImageFont.truetype(FONT_PATH_BOLD, 28)
    text_font = ImageFont.truetype(FONT_PATH_REG, 24)
    comment_font = ImageFont.truetype(FONT_PATH_REG, 20) 
    small_font = ImageFont.truetype(FONT_PATH_REG, 18)
    score_font = ImageFont.truetype(FONT_PATH_BOLD, 80)
    script_font = ImageFont.truetype(FONT_PATH_BOLD, 22) 
except:
    title_font = ImageFont.load_default()
    subtitle_font = ImageFont.load_default()
    text_font = ImageFont.load_default()
    comment_font = ImageFont.load_default()
    small_font = ImageFont.load_default()
    score_font = ImageFont.load_default()
    script_font = ImageFont.load_default()

# --- CSS 美化 ---
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 10px; background-color: #d63384; color: white; height: 3em; font-weight: bold; font-size: 1.2em; border: 2px solid #d63384;}
    .report-box { background-color: #fff0f6; padding: 20px; border-radius: 10px; border-left: 5px solid #d63384; color: #333; font-family: "Microsoft JhengHei";}
    .fengshui-box { background-color: #fff3cd; padding: 15px; border-radius: 5px; border-left: 5px solid #ffc107; margin-top: 10px; color: #856404;}
    .god-mode-box { background-color: #e3f2fd; padding: 15px; border-radius: 5px; border-left: 5px solid #2196f3; color: #0d47a1; margin-bottom: 20px;}
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
        
        # 確保有成本底價欄位，並轉為數字
        if '成本底價' in df.columns:
             df['成本底價'] = df['成本底價'].astype(str).str.replace(',', '').str.replace('$', '').astype(float).astype(int)
             
        return df, "SUCCESS"
    except Exception as e: return pd.DataFrame(), f"ERROR: {str(e)}"

def get_best_model(api_key):
    genai.configure(api_key=api_key)
    try:
        prefs = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro'] 
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        for p in prefs:
            if p in available: return p
        return available[0] if available else None
    except: return None

# ==========================================
# 2. AI 核心
# ==========================================
def get_analysis(api_key, image, user_price, car_info):
    target_model = get_best_model(api_key)
    if not target_model: return None, "找不到可用模型"

    if car_info:
        name = car_info.get('車款名稱', '未知')
        cost = car_info.get('成本底價', 0)
        margin = int(user_price * 10000) - cost
        context = f"數據庫匹配：{name}，底價${cost}，賣家開價${int(user_price*10000)}，價差${margin}。"
    else:
        context = "無庫存數據，請僅憑照片進行外觀估價。"

    prompt = f"""
    你現在是 Elon Musk，也是一位懂台灣民俗的科技算命師。
    {context}

    請回傳純 JSON (繁體中文)：
    - "car_model": "車型",
    - "sucker_score": 0-100 (盤子指數),
    - "margin_analysis": "價差短評 (請嚴格控制在 6 個字以內，例如：暴利收割、合理行情、佛心賣家)",
    - "verdict_short": "決策 (BUY IT / NEGOTIATE / RUN)",
    - "musk_comment": "馬斯克毒舌短評 (約 50 字)",
    - "feng_shui": "請根據車色或外型，瞎掰一個『賽博風水運勢』。例如：黑色屬水帶財，適合工程師；或是紅色煞氣重，小心罰單。(約30字)",
    - "line_msg_polite": "寫一則給賣家的 LINE 訊息(禮貌版)，用來探口風殺價。",
    - "line_msg_aggressive": "寫一則給賣家的 LINE 訊息(老司機版)，直接亮底牌殺價。"
    """
    
    try:
        model = genai.GenerativeModel(target_model)
        response = model.generate_content([prompt, image])
        txt = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(txt), target_model
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg: 
            return None, "RATE_LIMIT"
        return None, error_msg

# ==========================================
# 3. 圖片生成引擎 (V28：底價移除版)
# ==========================================
def create_report_card(car_image, ai_data, user_price, car_info):
    W, H = 850, 1300 # 高度維持 1300，空間很夠
    bg_color = (25, 20, 35)
    card = Image.new('RGB', (W, H), bg_color)
    draw = ImageDraw.Draw(card)

    car_img_resized = car_image.resize((810, 500))
    card.paste(car_img_resized, (20, 100))

    draw.text((20, 25), "BRIAN AI | 智能戰情室 X 運勢分析", font=title_font, fill=(255, 0, 255))
    draw.line((20, 80, 830, 80), fill=(255, 0, 255), width=3)

    # --- 第一層：數據區 (Y=630) ---
    score = ai_data.get('sucker_score', 50)
    score_color = (255, 50, 50) if score > 70 else (0, 255, 0)
    draw.text((40, 630), "盤子指數", font=text_font, fill=(200, 200, 200))
    draw.text((40, 670), str(score), font=score_font, fill=score_color)

    margin_text = ai_data.get('margin_analysis', '分析中')
    draw.text((360, 630), "利潤結構", font=text_font, fill=(200, 200, 200))
    margin_lines = textwrap.wrap(margin_text, width=10) 
    y_margin = 675
    for line in margin_lines:
        draw.text((360, y_margin), line, font=subtitle_font, fill=(255, 255, 255))
        y_margin += 35

    draw.text((620, 630), "賣家開價", font=text_font, fill=(200, 200, 200))
    draw.text((620, 675), f"${user_price}萬", font=subtitle_font, fill=(255, 255, 255))

    # --- 關鍵修改：完全不顯示底價 ---
    # (原本在這裡的底價顯示代碼已經刪除)
    # 這裡只留一個空的佔位，或是什麼都不放，讓畫面乾淨

    # --- 第二層：馬斯克評語 (維持 Y=830) ---
    START_Y_MUSK = 830 
    
    verdict = ai_data.get('verdict_short', 'N/A').upper()
    verdict_color = (255, 50, 50) if "RUN" in verdict else (0, 255, 0)
    
    # 決策印章
    draw.rectangle((40, START_Y_MUSK, 320, START_Y_MUSK + 70), outline=verdict_color, width=4)
    draw.text((60, START_Y_MUSK + 15), verdict, font=title_font, fill=verdict_color)

    # 評語文字
    comment = ai_data.get('musk_comment', '...')
    x_comment = 360
    lines = textwrap.wrap(comment, width=23) 
    y_text = START_Y_MUSK 
    draw.text((x_comment, y_text-30), "Elon's Verdict:", font=small_font, fill=(255, 0, 255))
    for line in lines:
        draw.text((x_comment, y_text), line, font=comment_font, fill=(230, 230, 230))
        y_text += 30

    # --- 第三層：風水分析 (維持 Y=1050) ---
    START_Y_FENGSHUI = 1050
    draw.line((20, START_Y_FENGSHUI - 20, 830, START_Y_FENGSHUI - 20), fill=(100, 100, 100), width=1)
    
    feng_shui = ai_data.get('feng_shui', '分析中...')
    draw.text((20, START_Y_FENGSHUI), "🔮 Cyber Feng Shui (賽博風水)", font=subtitle_font, fill=(255, 215, 0))
    
    fs_lines = textwrap.wrap(feng_shui, width=32)
    y_fs = START_Y_FENGSHUI + 50
    for line in fs_lines:
        draw.text((40, y_fs), line, font=text_font, fill=(255, 255, 200))
        y_fs += 35

    draw.text((20, 1250), "Powered by Brian's AI | 買車看數據，也看天意", font=small_font, fill=(100, 100, 100))
    return card

# ==========================================
# 4. 主程式介面
# ==========================================
def main():
    with st.sidebar:
        st.header("🦅 控制台")
        mode = st.radio("🤔 選擇模式：", ["自行搜尋 (老手)", "AI 幫我抽 (懶人)"])
        st.markdown("---")

        if "GOOGLE_API_KEY" in st.secrets:
            api_key = st.secrets["GOOGLE_API_KEY"]
            st.success("✅ API 金鑰已啟用")
        else:
            api_key = st.text_input("Google API Key", type="password")
            
        st.caption("V28 (底價神隱版)")

    st.title("🦅 拍賣場 AI 戰情室")

    df, status = load_data()
    selected_car_info = None

    # ==========================
    # 模式 A: AI 幫我抽 (懶人)
    # ==========================
    if mode == "AI 幫我抽 (懶人)":
        st.markdown("<div class='god-mode-box'><b>🎲 AI 靈籤模式：</b><br>不知道買什麼？輸入預算，讓 AI 幫你決定命運。</div>", unsafe_allow_html=True)
        
        col_a, col_b = st.columns(2)
        with col_a:
            budget_limit = st.slider("💰 預算上限 (萬)", 10, 300, 50)
        with col_b:
            usage_goal = st.selectbox("🎯 用車目的", ["純代步 (省油就好)", "把妹 (要帥)", "載家人 (要大)", "跑山 (要快)", "練車 (撞了不心疼)"])

        if st.button("🔮 幫我抽一台！"):
            if status != "SUCCESS":
                st.error("⚠️ 資料庫未連線，無法抽籤。")
            else:
                try:
                    candidates = df[df['成本底價'] <= (budget_limit * 10000)].copy()
                    if not candidates.empty:
                        lucky_car = candidates.sample(1).iloc[0]
                        st.session_state['god_car'] = lucky_car.to_dict()
                        st.session_state['user_usage'] = usage_goal
                        st.balloons()
                    else:
                        st.error("❌ 預算太低了... 買不到車！")
                except Exception as e:
                    st.error(f"抽籤失敗：{str(e)}")

        if 'god_car' in st.session_state:
            car = st.session_state['god_car']
            st.success(f"🎉 天選之車：**{car['車款名稱']}**")
            st.info(f"💡 請去網路上找 **{car['車款名稱']}** 的照片，切換回「自行搜尋」模式進行詳細分析！")

    # ==========================
    # 模式 B: 自行搜尋 (Manual)
    # ==========================
    else:
        if status == "SUCCESS" and not df.empty:
            car_options = ["--- 搜尋庫存資料 (選填) ---"] + df['車款名稱'].astype(str).tolist()
            selected_option = st.selectbox("🔍 關鍵字搜尋:", car_options)
            if selected_option != "--- 搜尋庫存資料 (選填) ---":
                row = df[df['車款名稱'] == selected_option].iloc[0]
                selected_car_info = row.to_dict()
                st.info(f"🎯 鎖定：{row['車款名稱']} | 📜 行情數據庫：✅ 已連線 (底價隱藏中)")
        else:
            if status == "MISSING": st.warning("⚠️ 進入純 AI 模式 (無庫存比對)")
            
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            price_input = st.number_input("賣家開價 (萬)", 1.0, 500.0, 60.0, step=0.5)
        with col2:
            st.caption(" ")
            st.caption("💡 上傳照片後，AI 將結合數據庫與面相學進行綜合分析。")

        uploaded_file = st.file_uploader("📸 上傳車輛照片", type=['jpg', 'png', 'jpeg'])

        if uploaded_file and api_key:
            image = Image.open(uploaded_file)
            st.image(image, caption='待鑑價車輛', width=300)
            
            # --- V25 防手賤冷卻機制 ---
            current_time = time.time()
            last_click_time = st.session_state.get('last_click_time', 0)
            COOLDOWN_SECONDS = 15 

            generate_btn = st.button("🚀 生成全方位鑑價報告")

            if generate_btn:
                if current_time - last_click_time < COOLDOWN_SECONDS:
                    wait_time = int(COOLDOWN_SECONDS - (current_time - last_click_time))
                    st.warning(f"❄️ 技能冷卻中！馬斯克罵人很累，請等待 {wait_time} 秒後再試...")
                else:
                    st.session_state['last_click_time'] = current_time
                    
                    with st.spinner("🔮 馬斯克正在計算盤子指數 & 觀看星象..."):
                        ai_data, error_status = get_analysis(api_key, image, price_input, selected_car_info)
                        
                        if ai_data:
                            st.markdown(f"<div class='fengshui-box'>🔮 <b>賽博風水分析：</b><br>{ai_data.get('feng_shui')}</div>", unsafe_allow_html=True)

                            st.markdown("### 💬 幫你寫好 LINE 訊息：")
                            tab1, tab2 = st.tabs(["😇 禮貌試探版", "😎 老司機殺價版"])
                            with tab1: st.code(ai_data.get('line_msg_polite'), language="text")
                            with tab2: st.code(ai_data.get('line_msg_aggressive'), language="text")

                            report_card = create_report_card(image, ai_data, price_input, selected_car_info)
                            st.image(report_card, caption="✅ 您的全方位戰情卡", use_column_width=True)
                            
                            buf = io.BytesIO()
                            report_card.save(buf, format="PNG")
                            st.download_button(label="📥 下載圖卡 (發 Threads 用)", data=buf.getvalue(), file_name="Musk_FengShui.png", mime="image/png")
                        
                        else:
                            if error_status == "RATE_LIMIT":
                                st.warning("🔥 系統過熱中！太多人在玩了，請排隊稍等 1 分鐘！")
                            else:
                                st.error(f"❌ 分析失敗：{error_status}")

        elif not api_key:
            st.warning("👈 請輸入 API Key")

if __name__ == "__main__":
    main()
