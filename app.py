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
st.set_page_config(page_title="Brian AI 戰情室 (V30-智慧輸入版)", page_icon="🦅", layout="centered")

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
    .smart-input-box { background-color: #e8f5e9; padding: 15px; border-radius: 10px; border-left: 5px solid #4caf50; margin-bottom: 20px;}
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
# 2. AI 核心功能
# ==========================================

# --- 新增功能：從雜亂文字中提取車型與價格 ---
def extract_info_from_text(api_key, raw_text):
    target_model = get_best_model(api_key)
    if not target_model: return None
    
    prompt = f"""
    你是資料提取機器人。使用者會輸入一段關於賣車的文字（可能是標題、貼文、或對話）。
    請從中提取：
    1. "car_name": 車款名稱 (盡量完整，例如 '2016 Toyota Altis')
    2. "price": 價格 (單位換算為『萬』，純數字。例如 358000 請轉為 35.8。如果沒寫價格，回傳 0)
    
    使用者輸入：{raw_text}
    
    請回傳純 JSON 格式：{{"car_name": "...", "price": 0.0}}
    """
    try:
        model = genai.GenerativeModel(target_model)
        response = model.generate_content(prompt)
        txt = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(txt)
    except:
        return None

# --- 原本的分析核心 ---
def get_analysis(api_key, image, user_price, car_info, manual_car_name=None):
    target_model = get_best_model(api_key)
    if not target_model: return None, "找不到可用模型"

    # 數據與情境準備
    if car_info:
        name = car_info.get('車款名稱', '未知')
        cost = car_info.get('成本底價', 0)
        margin = int(user_price * 10000) - cost
        db_context = f"數據庫匹配：{name}，底價${cost}，賣家開價${int(user_price*10000)}，價差${margin}。"
    else:
        name = manual_car_name if manual_car_name else "未知車款"
        db_context = f"使用者輸入車款：{name}，開價${user_price}萬 (無數據庫底價參考)。"

    if image:
        image_context = "請根據『上傳的照片』進行外觀與車況的毒舌分析。"
        input_content = [image]
    else:
        image_context = f"使用者【沒有上傳照片】，請你發揮想像力，假設這是一台市面上常見的 {name} 中古車。請根據它的價格和車型進行『盲測毒舌』。"
        input_content = []

    prompt = f"""
    你現在是 Elon Musk，也是一位懂台灣民俗的科技算命師。
    {db_context}
    {image_context}

    請回傳純 JSON (繁體中文)：
    - "car_model": "車型",
    - "sucker_score": 0-100 (盤子指數),
    - "margin_analysis": "價差短評 (請嚴格控制在 6 個字以內，例如：暴利收割、合理行情、佛心賣家)",
    - "verdict_short": "決策 (BUY IT / NEGOTIATE / RUN)",
    - "musk_comment": "馬斯克毒舌短評 (約 50 字)",
    - "feng_shui": "請瞎掰一個『賽博風水運勢』。例如：沒照片我看不到氣場，但這價格八成是兇車；或是這價格太便宜，肯定有鬼。(約30字)",
    - "line_msg_polite": "寫一則給賣家的 LINE 訊息(禮貌版)，用來探口風殺價。",
    - "line_msg_aggressive": "寫一則給賣家的 LINE 訊息(老司機版)，直接亮底牌殺價。"
    """
    
    input_content.insert(0, prompt)

    try:
        model = genai.GenerativeModel(target_model)
        response = model.generate_content(input_content)
        txt = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(txt), target_model
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg: return None, "RATE_LIMIT"
        return None, error_msg

# ==========================================
# 3. 圖片生成引擎
# ==========================================
def create_report_card(car_image, ai_data, user_price, car_info):
    W, H = 850, 1300 
    bg_color = (25, 20, 35)
    card = Image.new('RGB', (W, H), bg_color)
    draw = ImageDraw.Draw(card)

    if car_image:
        car_img_resized = car_image.resize((810, 500))
        card.paste(car_img_resized, (20, 100))
    else:
        draw.rectangle((20, 100, 830, 600), fill=(50, 50, 50))
        draw.text((250, 300), "NO IMAGE UPLOADED", font=subtitle_font, fill=(100, 100, 100))
        draw.text((280, 350), "(盲測模式)", font=title_font, fill=(150, 150, 150))

    draw.text((20, 25), "BRIAN AI | 智能戰情室 X 運勢分析", font=title_font, fill=(255, 0, 255))
    draw.line((20, 80, 830, 80), fill=(255, 0, 255), width=3)

    # 數據區
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

    # 馬斯克評語 (無底價顯示)
    START_Y_MUSK = 830 
    verdict = ai_data.get('verdict_short', 'N/A').upper()
    verdict_color = (255, 50, 50) if "RUN" in verdict else (0, 255, 0)
    
    draw.rectangle((40, START_Y_MUSK, 320, START_Y_MUSK + 70), outline=verdict_color, width=4)
    draw.text((60, START_Y_MUSK + 15), verdict, font=title_font, fill=verdict_color)

    comment = ai_data.get('musk_comment', '...')
    x_comment = 360
    lines = textwrap.wrap(comment, width=23) 
    y_text = START_Y_MUSK 
    draw.text((x_comment, y_text-30), "Elon's Verdict:", font=small_font, fill=(255, 0, 255))
    for line in lines:
        draw.text((x_comment, y_text), line, font=comment_font, fill=(230, 230, 230))
        y_text += 30

    # 風水區
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
        mode = st.radio("🤔 選擇模式：", ["自行搜尋 (AI 智慧輸入)", "AI 幫我抽 (懶人)"])
        st.markdown("---")
        if "GOOGLE_API_KEY" in st.secrets:
            api_key = st.secrets["GOOGLE_API_KEY"]
            st.success("✅ API 金鑰已啟用")
        else:
            api_key = st.text_input("Google API Key", type="password")
        st.caption("V30 (智慧輸入版)")

    st.title("🦅 拍賣場 AI 戰情室")
    df, status = load_data()
    selected_car_info = None

    # === Mode A: 抽籤 (保持不變) ===
    if mode == "AI 幫我抽 (懶人)":
        st.markdown("<div class='god-mode-box'><b>🎲 AI 靈籤模式：</b><br>不知道買什麼？輸入預算，讓 AI 幫你決定命運。</div>", unsafe_allow_html=True)
        col_a, col_b = st.columns(2)
        with col_a: budget_limit = st.slider("💰 預算上限 (萬)", 10, 300, 50)
        with col_b: usage_goal = st.selectbox("🎯 用車目的", ["純代步 (省油就好)", "把妹 (要帥)", "載家人 (要大)", "跑山 (要快)", "練車 (撞了不心疼)"])
        
        if st.button("🔮 幫我抽一台！"):
            try:
                candidates = df[df['成本底價'] <= (budget_limit * 10000)].copy()
                if not candidates.empty:
                    lucky_car = candidates.sample(1).iloc[0]
                    st.session_state['god_car'] = lucky_car.to_dict()
                    st.balloons()
                    st.success(f"🎉 天選之車：**{lucky_car['車款名稱']}**")
                    st.info(f"💡 切換回「自行搜尋」模式，直接貼上 **{lucky_car['車款名稱']}** 來分析！")
                else: st.error("❌ 預算太低了... 買不到車！")
            except: st.error("抽籤失敗")

    # === Mode B: 智慧搜尋 (大幅改版) ===
    else:
        st.markdown("### 🚀 智慧輸入 (貼上文字即可)")
        
        # 1. 智慧輸入框
        smart_text = st.text_area("📋 直接貼上 8891 標題、FB 貼文、或朋友的訊息 (AI 會自己讀)", height=100, placeholder="例如：售 2015 Mazda 3 頂級款 里程8萬 只要35.8萬 誠可議")
        
        # 2. 手動微調區 (預設收合)
        with st.expander("🛠️ 手動微調 (如果 AI 讀錯請點這)", expanded=False):
            # 優先搜尋資料庫
            car_options = ["--- 未選擇 ---"] + (df['車款名稱'].astype(str).tolist() if not df.empty else [])
            selected_option = st.selectbox("資料庫匹配:", car_options)
            
            # 手動輸入
            manual_car_input = st.text_input("或手動輸入車型:", value="")
            manual_price_input = st.number_input("價格 (萬):", 0.0, 1000.0, 0.0, step=0.5)

        # 3. 照片上傳 (選填)
        uploaded_file = st.file_uploader("📸 上傳截圖/照片 (選填，有圖更準)", type=['jpg', 'png', 'jpeg'])
        image = Image.open(uploaded_file) if uploaded_file else None

        # 4. 執行邏輯
        if api_key:
            # 防手賤冷卻
            current_time = time.time()
            last_click_time = st.session_state.get('last_click_time', 0)
            COOLDOWN_SECONDS = 10
            
            if st.button("🔥 開始毒舌分析"):
                if current_time - last_click_time < COOLDOWN_SECONDS:
                    st.warning(f"❄️ 馬斯克還在喘... 請等 {int(COOLDOWN_SECONDS - (current_time - last_click_time))} 秒")
                else:
                    st.session_state['last_click_time'] = current_time
                    
                    # --- 階段一：解析資料 ---
                    final_car_name = ""
                    final_price = 0.0
                    
                    with st.spinner("🤖 AI 正在閱讀你貼的文字..."):
                        # 如果有智慧文字，先解析
                        if smart_text:
                            extracted = extract_info_from_text(api_key, smart_text)
                            if extracted:
                                final_car_name = extracted.get("car_name", "")
                                final_price = float(extracted.get("price", 0.0))
                                st.success(f"✅ AI 讀取到：{final_car_name} | ${final_price}萬")
                        
                        # 如果手動輸入區有值，覆蓋 AI 的判斷 (User override)
                        if selected_option != "--- 未選擇 ---":
                            final_car_name = selected_option
                        elif manual_car_input:
                            final_car_name = manual_car_input
                            
                        if manual_price_input > 0:
                            final_price = manual_price_input

                    # --- 階段二：嘗試匹配資料庫底價 ---
                    matched_row = None
                    if not df.empty and final_car_name:
                        # 簡單模糊比對 (如果資料庫有這個名字)
                        matches = df[df['車款名稱'].astype(str).str.contains(final_car_name, case=False, na=False)]
                        if not matches.empty:
                            matched_row = matches.iloc[0].to_dict()
                            st.info(f"📚 成功匹配庫存數據：{matched_row['車款名稱']} (底價參考中)")
                        else:
                            st.caption(f"⚠️ 無法在資料庫找到 '{final_car_name}'，將進行盲測模式。")

                    # --- 階段三：生成報告 ---
                    if not final_car_name:
                        st.error("❌ AI 看不懂你貼了什麼，請手動輸入車名！")
                    elif final_price <= 0:
                        st.error("❌ 沒抓到價格？請手動補上價格！")
                    else:
                        with st.spinner("🔮 馬斯克正在開噴..."):
                            ai_data, error_status = get_analysis(api_key, image, final_price, matched_row, final_car_name)
                            
                            if ai_data:
                                st.markdown(f"<div class='fengshui-box'>🔮 <b>賽博風水：</b>{ai_data.get('feng_shui')}</div>", unsafe_allow_html=True)
                                
                                tab1, tab2 = st.tabs(["😇 禮貌版", "😎 殺價版"])
                                with tab1: st.code(ai_data.get('line_msg_polite'), language="text")
                                with tab2: st.code(ai_data.get('line_msg_aggressive'), language="text")

                                report_card = create_report_card(image, ai_data, final_price, matched_row)
                                st.image(report_card, caption="✅ 戰情卡", use_column_width=True)
                                
                                buf = io.BytesIO()
                                report_card.save(buf, format="PNG")
                                st.download_button("📥 下載圖卡", buf.getvalue(), "Musk_Roast.png", "image/png")
                            else:
                                if error_status == "RATE_LIMIT": st.warning("🔥 系統過熱，請排隊！")
                                else: st.error(f"❌ 失敗：{error_status}")

        elif not api_key:
            st.warning("👈 請輸入 API Key")

if __name__ == "__main__":
    main()

