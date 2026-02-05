import streamlit as st
import openai
import requests
import serial
import time
from streamlit_mic_recorder import speech_to_text

# ==========================================
# 👇 수정된 import (같은 폴더에 있을 때)
# ==========================================
from ai_generator import translate_prompt, generate_image
from image_proc import process_image_to_sketch
from gcode_utils import image_to_gcode

# ==========================================
# ⚙️ 아두이노 포트 설정 (라즈베리 파이 연결용)
# ==========================================
SERIAL_PORT = 'COM6'  # 아까 확인한 포트 (안 되면 /dev/ttyUSB0 시도)
BAUD_RATE = 115200

# ==========================================
# 🔐 API 키 설정
# ==========================================
try:
    openai.api_key = st.secrets["OPENAI_API_KEY"]
    client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except Exception as e:
    st.error(f"🚨 API Key 오류! .streamlit/secrets.toml 파일을 확인하세요.\n내용: {e}")
    st.stop()

# ==========================================
# 🔌 아두이노 전송 함수
# ==========================================
def send_to_arduino(gcode_text):
    try:
        # 1. 아두이노 연결
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        time.sleep(2) # 연결 대기 (아두이노 리셋 방지)

        lines = gcode_text.strip().split('\n')
        total_lines = len(lines)
        
        # 화면에 진행바 띄우기
        progress_bar = st.progress(0)
        status_text = st.empty()

        for i, line in enumerate(lines):
            if not line.strip(): continue

            # 명령 전송
            ser.write((line + '\n').encode())

            # 아두이노가 'ok' 할 때까지 대기 (흐름 제어)
            while True:
                response = ser.readline().decode().strip()
                if 'ok' in response:
                    break
            
            # 진행률 업데이트
            current_progress = (i + 1) / total_lines
            progress_bar.progress(current_progress)
            status_text.text(f"🖨️ 출력 중... ({int(current_progress * 100)}%)")

        ser.close()
        return True, "출력 완료! 작품을 확인하세요."

    except Exception as e:
        return False, f"전송 실패 (케이블 확인 필요): {str(e)}"

# ==========================================
# 🖥️ 화면 구성
# ==========================================
st.set_page_config(page_title="AI Plotter Final", page_icon="✒️")
st.title("✒️ AI 플로터 (IoT 버전)")

# 스타일 선택
style_option = st.radio(
    "드로잉 스타일:", 
    ('1. 〰️ 원라인', '2. 🖍️ 캐릭터 (스텐실)', '3. 📐 V3 지오메트릭'), 
    horizontal=True
)

# 프롬프트 설정
style_modifier = ""
if '원라인' in style_option:
    style_modifier = ", continuous single line drawing, minimalist, fluid line art, flat pure white background, no shading, vector style."
elif '캐릭터' in style_option:
    style_modifier = ", minimalist line art icon. vector style. smooth curves. monoline. black and white. no shading. high contrast. white background."
elif '지오메트릭' in style_option:
    style_modifier = ", minimalist geometric low poly vector art. Constructed with large, sparse triangles. Single straight black lines. No shading. Isolated on white background."

# 입력 받기
c1, c2 = st.columns([1, 4])
with c1: st.write("🎤 음성:")
with c2: 
    voice = speech_to_text(language='ko', start_prompt="🔴 말하기", stop_prompt="⏹️ 끝", key='STT')

if 'voice_msg' not in st.session_state:
    st.session_state.voice_msg = ""

if voice:
    if isinstance(voice, dict):
        st.session_state.voice_msg = voice.get("text", "")
    else:
        st.session_state.voice_msg = str(voice)

user_prompt = st.text_input("그릴 내용:", value=st.session_state.voice_msg)

st.divider()

# ==========================================
# 🚀 1. 이미지 생성 및 G-code 변환
# ==========================================
if st.button("🎨 1단계: 그림 생성하기", type="primary", use_container_width=True):
    if not user_prompt:
        st.warning("⚠️ 내용을 입력해주세요!")
    else:
        # [단계 1] 번역
        with st.spinner("번역 중..."):
            eng_prompt = translate_prompt(client, user_prompt)
        
        if "Error" in eng_prompt:
            st.error(f"🚨 번역 에러: {eng_prompt}")
        else:
            st.info(f"🔤 번역: {eng_prompt}")
            
            # [단계 2] 그림 생성
            with st.spinner("그림 그리는 중 (DALL-E)..."):
                img_url = generate_image(client, eng_prompt, style_modifier)
            
            if img_url:
                img_data = requests.get(img_url).content
                st.session_state.generated_image = img_data
                
                # [단계 3] 전처리
                processed_data = process_image_to_sketch(img_data)
                if processed_data:
                    st.session_state.processed_image = processed_data
                    
                    # [단계 4] G-code 변환 (미리 해둠)
                    gcode_result = image_to_gcode(st.session_state.processed_image)
                    if "Error" not in gcode_result:
                        st.session_state.gcode_result = gcode_result
                        st.success("✅ 이미지 생성 및 G-code 준비 완료!")
                    else:
                        st.error(f"G-code 변환 실패: {gcode_result}")
                else:
                    st.error("전처리 실패")
            else:
                st.error("이미지 생성 실패")

# ==========================================
# 🖼️ 2. 결과 확인 및 실제 출력
# ==========================================
if 'generated_image' in st.session_state and 'processed_image' in st.session_state:
    col1, col2 = st.columns(2)
    with col1:
        st.image(st.session_state.generated_image, caption="AI 원본")
    with col2:
        st.image(st.session_state.processed_image, caption="플로터용 전처리")
        
    st.divider()
    
    # G-code가 준비되었다면 출력 버튼 표시
    if 'gcode_result' in st.session_state:
        st.warning("⚠️ 주의: 기계가 움직입니다! 손을 가까이 하지 마세요.")
        
        if st.button("🖨️ 2단계: 종이에 그리기 (출력 시작)", type="primary"):
            with st.spinner('기계로 전송 중...'):
                success, msg = send_to_arduino(st.session_state.gcode_result)
                
            if success:
                st.balloons()
                st.success(msg)
            else:
                st.error(msg)
        
        # 다운로드 버튼도 살려둠 (백업용)
        st.download_button("💾 G-code 파일만 다운로드", st.session_state.gcode_result, "plot.gcode")

