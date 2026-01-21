import streamlit as st
import openai
from io import BytesIO
import requests
from PIL import Image, ImageOps
from streamlit_mic_recorder import mic_recorder
import cv2
import numpy as np

# ==========================================
# 🔐 API 키 설정 (OpenAI 하나로 통일!)
# ==========================================
try:
    # secrets.toml에 있는 OPENAI_API_KEY 사용
    openai.api_key = st.secrets["OPENAI_API_KEY"]
    client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except Exception as e:
    st.error(f"OpenAI API 키 오류! secrets.toml을 확인해주세요.\n에러: {e}")
    st.stop()

# ==========================================
# 🧠 [통역사] GPT-4o-mini (번역 담당)
# ==========================================
def translate_to_english_gpt(text):
    try:
        # [핵심 수정] 한국어는 번역하고, 영어는 다듬어주는 똑똑한 프롬프트 적용!
        system_prompt = """You are an expert prompt engineer for DALL-E. 
        Your task is to convert user input into a descriptive English prompt for image generation.
        1. If the input is in Korean, translate it accurately into English.
        2. If the input is already in English, refine it to be more descriptive for DALL-E.
        Output ONLY the final English prompt string."""
        
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
# 🎤 [귀] Whisper-1 (음성 인식 담당)
# ==========================================
def transcribe_audio_whisper(audio_bytes):
    try:
        audio_file = BytesIO(audio_bytes)
        audio_file.name = "voice.wav"
        
        # [유지] 한국어 인식률 최우선을 위해 language="ko" 고정
        # 영어를 말해도 Whisper가 알아서 한국어로 음차( transliteration)하거나
        # 쉬운 단어는 영어로 적어주는데, 이걸 위에서 GPT가 알아서 처리함.
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="ko"
        )
        return transcript.text.strip()
    except Exception as e:
        st.error(f"음성 인식 실패: {e}")
        return ""

# ==========================================
# 📸 [손] DALL-E 2 (그림 담당)
# ==========================================
def generate_dalle_image(english_prompt):
    try:
        # 실사 느낌을 강조하는 프롬프트 추가
        full_prompt = f"{english_prompt}, photorealistic photograph, detailed, sharp focus, white background."
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
# 🎨 [변환기] 이미지 -> 스케치 (OpenCV)
# ==========================================
def convert_to_sketch(image_bytes):
    # 1. 이미지 로드
    file_bytes = np.asarray(bytearray(image_bytes), dtype=np.uint8)
    image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    
    # 2. 흑백 변환 및 블러 (노이즈 제거)
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred_image = cv2.GaussianBlur(gray_image, (5, 5), 0)
    
    # 3. Canny Edge Detection (외곽선 검출)
    # threshold1, 2 값을 조절하면 선의 디테일이 달라집니다. (현재 50, 150)
    edges = cv2.Canny(blurred_image, 50, 150)
    
    # 4. 색상 반전 (검은 배경 흰 선 -> 흰 배경 검은 선 - 플로터용)
    inverted_edges = cv2.bitwise_not(edges)
    
    # 5. 결과 반환
    is_success, buffer = cv2.imencode(".png", inverted_edges)
    return buffer.tobytes()

# ==========================================
# 🖥️ 메인 UI
# ==========================================
st.set_page_config(page_title="AI Plotter Controller", page_icon="🤖")
st.title("🤖 AI 플로터 컨트롤러 (통합 버전)")
st.caption("OpenAI(음성/번역/그림) + OpenCV(스케치 변환) 엔진 탑재")

st.divider()

# --- 1. 음성 입력 ---
c1, c2 = st.columns([1, 4])
with c1:
    st.write("🎤 음성 명령:")
with c2:
    audio = mic_recorder(start_prompt="🔴 녹음 시작", stop_prompt="⏹ 녹음 종료", just_once=True, key='rec')

if 'voice_msg' not in st.session_state:
    st.session_state.voice_msg = ""

if audio:
    with st.spinner("Whisper가 듣는 중..."):
        st.session_state.voice_msg = transcribe_audio_whisper(audio['bytes'])

user_prompt = st.text_input("주제 입력 (한글/영어):", value=st.session_state.voice_msg)

st.divider()

# --- 2. 이미지 생성 버튼 ---
if st.button("📸 실사 이미지 생성하기 (DALL-E 2)", type="primary", use_container_width=True):
    if not user_prompt:
        st.warning("주제를 입력해주세요!")
    else:
        # 1단계: 번역 (GPT-4o-mini)
        with st.spinner("GPT가 DALL-E를 위한 프롬프트를 작성 중..."):
            english_prompt = translate_to_english_gpt(user_prompt)
        
        if english_prompt.startswith("Error"):
            st.error(f"🛑 프롬프트 작성 실패: {english_prompt}")
        else:
            st.info(f"🔤 DALL-E 프롬프트: **[{english_prompt}]**")

            # 2단계: 그림 (DALL-E 2)
            with st.spinner(f"DALL-E 2가 그리는 중... (약 20원)"):
                img_url = generate_dalle_image(english_prompt)
                
                if img_url:
                    img_data = requests.get(img_url).content
                    st.session_state.generated_image = img_data
                    # 새 그림 생성 시 기존 변환 결과 초기화
                    if 'processed_image' in st.session_state:
                        del st.session_state.processed_image
                    st.success("생성 완료!")

# --- 3. 결과 확인 및 변환 ---
if 'generated_image' in st.session_state:
    st.image(st.session_state.generated_image, caption="원본 실사 이미지", use_container_width=True)
    
    st.divider()
    st.subheader("🎨 플로터용 변환 스타일 선택")
    
    b1, b2, b3 = st.columns(3)
    
    with b1:
        if st.button("📐 지오메트릭", use_container_width=True):
            st.info("🚧 다음 업데이트 예정 (Next Step!)")
            
    with b2:
        if st.button("〰️ 원라인", use_container_width=True):
             st.info("🚧 다음 업데이트 예정 (Next Step!)")
            
    with b3:
        # OpenCV 스케치 버튼
        if st.button("🖊️ 스케치 (Edge)", type="secondary", use_container_width=True):
            with st.spinner("OpenCV가 외곽선을 추출하는 중..."):
                processed_data = convert_to_sketch(st.session_state.generated_image)
                st.session_state.processed_image = processed_data
                st.toast("✅ 스케치 변환 완료!")

    # 변환된 이미지가 있으면 표시
    if 'processed_image' in st.session_state:
        st.divider()
        st.subheader("🖨️ 플로터 출력 결과물 (Preview)")
        st.image(st.session_state.processed_image, caption="최종 변환 결과 (Canny Edge)", use_container_width=True)