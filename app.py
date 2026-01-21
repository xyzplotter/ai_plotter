import streamlit as st
import openai
import requests
import cv2
import numpy as np
from PIL import Image
# 브라우저 내장 음성 인식 (무료, 자동/수동 종료)
from streamlit_mic_recorder import speech_to_text

# ==========================================
# 🔐 1. API 키 설정
# ==========================================
try:
    openai.api_key = st.secrets["OPENAI_API_KEY"]
    client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except Exception as e:
    st.error(f"🚨 OpenAI API 키 오류! Streamlit 설정(Secrets)을 확인해주세요.\n에러 내용: {e}")
    st.stop()

# ==========================================
# 🧠 2. 프롬프트 엔지니어링 (GPT-4o-mini)
# ==========================================
def translate_to_english_gpt(text):
    try:
        # [핵심 변경] GPT에게 "플로터용 도안"을 만들라고 강력하게 지시
        system_prompt = """You are an expert prompt engineer for a pen plotter art bot.
        Your goal is to convert user input into a specific prompt for DALL-E to generate 'Line Art'.
        
        Strictly follow these rules to avoid 'hatching' (shading):
        1. Style: "Minimalist continuous line art", "Black ink on white background", "No shading", "No fill", "High contrast".
        2. Detail: "Vector style illustration", "Clean lines", "Simple shapes", "Coloring book style".
        3. Subject: Focus on the main object clearly.
        4. Output: ONLY output the final English prompt string."""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error: {e}"

# ==========================================
# 📸 3. 이미지 생성 (DALL-E 2)
# ==========================================
def generate_dalle_image(english_prompt):
    try:
        # [핵심 변경] 프롬프트 뒤에 '단순화' 주문을 덕지덕지 붙임
        full_prompt = f"{english_prompt}, minimalist vector line art, black and white, simple outlines, white background, no shading, high contrast."
        
        response = client.images.generate(
            model="dall-e-2",
            prompt=full_prompt,
            size="1024x1024",
            n=1
        )
        return response.data[0].url
    except Exception as e:
        st.error(f"이미지 생성 실패: {e}")
        return None

# ==========================================
# 🎨 4. 스케치 변환 (OpenCV)
# ==========================================
def convert_to_sketch(image_bytes):
    # 이미지를 흑백으로 읽기
    file_bytes = np.asarray(bytearray(image_bytes), dtype=np.uint8)
    image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    
    # 1. 흑백 변환
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # 2. 노이즈 제거 (블러링을 약간 세게 줌)
    blurred_image = cv2.GaussianBlur(gray_image, (5, 5), 0)
    
    # 3. 이진화 (검은색/흰색만 남기기) - 흐릿한 회색 선을 날려버림
    _, binary_image = cv2.threshold(blurred_image, 200, 255, cv2.THRESH_BINARY)
    
    # 4. 외곽선 추출 (Canny)
    edges = cv2.Canny(binary_image, 50, 150)
    
    # 5. 색상 반전 (흰 배경에 검은 선)
    inverted_edges = cv2.bitwise_not(edges)
    
    # 인코딩 후 반환
    is_success, buffer = cv2.imencode(".png", inverted_edges)
    return buffer.tobytes()

# ==========================================
# 🖥️ 5. 메인 UI
# ==========================================
st.set_page_config(page_title="AI Plotter - Line Art Edition", page_icon="✒️")
st.title("✒️ AI 플로터 (라인 아트 전용)")
st.caption("🗣️ 말하면 -> 🎨 깔끔한 선화(Line Art)로 그려줍니다.")

st.divider()

if 'voice_msg' not in st.session_state:
    st.session_state.voice_msg = ""

# --- 1. 음성 입력 ---
c1, c2 = st.columns([1, 4])
with c1:
    st.write("🎤 명령하기:")
with c2:
    text = speech_to_text(
        language='ko',
        start_prompt="🔴 말하기 (Click)",
        stop_prompt="👂 듣고 있어요... (Click to Stop)", 
        just_once=True,
        key='STT'
    )

if text:
    st.session_state.voice_msg = text
    st.toast("✅ 인식 완료!", icon="🗣️")

user_prompt = st.text_input("주제 입력:", value=st.session_state.voice_msg)

st.divider()

# --- 2. 생성 및 변환 ---
if st.button("🎨 도안 생성하기 (DALL-E 2)", type="primary", use_container_width=True):
    if not user_prompt:
        st.warning("주제를 입력해주세요!")
    else:
        # 1. 번역 및 프롬프트 최적화
        with st.spinner("GPT가 플로터용 명령어로 변환 중..."):
            english_prompt = translate_to_english_gpt(user_prompt)
        
        if english_prompt.startswith("Error"):
            st.error(f"에러: {english_prompt}")
        else:
            st.info(f"🔤 변환된 명령: {english_prompt}")

            # 2. 그림 생성
            with st.spinner("DALL-E가 선화(Line Art)를 그리는 중..."):
                img_url = generate_dalle_image(english_prompt)
                
                if img_url:
                    img_data = requests.get(img_url).content
                    st.session_state.generated_image = img_data
                    
                    # 3. 바로 스케치 변환까지 실행 (원스톱)
                    processed_data = convert_to_sketch(img_data)
                    st.session_state.processed_image = processed_data
                    st.success("생성 및 변환 완료!")

# --- 3. 결과 확인 ---
if 'generated_image' in st.session_state and 'processed_image' in st.session_state:
    col1, col2 = st.columns(2)
    with col1:
        st.image(st.session_state.generated_image, caption="1차 결과 (DALL-E Line Art)", use_container_width=True)
    with col2:
        st.image(st.session_state.processed_image, caption="최종 변환 (Plotter Ready)", use_container_width=True)
        
    st.download_button(
        label="📥 최종 이미지 다운로드",
        data=st.session_state.processed_image,
        file_name="plotter_sketch.png",
        mime="image/png",
        use_container_width=True
    )
