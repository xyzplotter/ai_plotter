import streamlit as st
import openai
import requests
from streamlit_mic_recorder import speech_to_text

# 모듈 불러오기
from modules.ai_generator import translate_prompt, generate_image
from modules.image_proc import process_image_to_sketch
from modules.gcode_utils import image_to_gcode

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
# 🖥️ 화면 구성
# ==========================================
st.set_page_config(page_title="AI Plotter Final", page_icon="✒️")
st.title("✒️ AI 플로터 (최종 디버깅 모드)")

# 스타일 선택
style_option = st.radio(
    "스타일:", 
    ('1. 〰️ 원라인', '2. 🖍️ 캐릭터 (스텐실)', '3. 📐 V3 지오메트릭'), 
    horizontal=True
)

# 프롬프트 설정
style_modifier = ""
if '원라인' in style_option:
    style_modifier = ", continuous single line drawing, minimalist, fluid line art, flat pure white background, no shading, vector style."
elif '캐릭터' in style_option:
    style_modifier = ", simple vector line art. Stencil style outline. Minimalist coloring book page. Thick monoline black outlines. White fill. No internal detail lines, no shading. Isolated on white background."
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
    st.session_state.voice_msg = voice

user_prompt = st.text_input("그릴 내용:", value=st.session_state.voice_msg)

st.divider()

# ==========================================
# 🚀 실행 로직 (디버깅 메시지 포함)
# ==========================================
if st.button("🎨 생성 시작", type="primary", use_container_width=True):
    # 1. 버튼 클릭 확인
    st.write("✅ 버튼이 클릭되었습니다. 처리를 시작합니다...")
    
    if not user_prompt:
        st.warning("⚠️ 내용을 입력해주세요!")
    else:
        # [단계 1] 번역
        with st.spinner("1단계: 번역 중..."):
            eng_prompt = translate_prompt(client, user_prompt)
        
        if "Error" in eng_prompt:
            st.error(f"🚨 번역 에러: {eng_prompt}")
        else:
            st.info(f"🔤 번역 결과: {eng_prompt}")
            
            # [단계 2] 그림 생성
            with st.spinner("2단계: 그림 그리는 중 (최대 10초)..."):
                img_url = generate_image(client, eng_prompt, style_modifier)
            
            if img_url:
                # 이미지 다운로드
                st.write("📸 이미지 다운로드 중...")
                img_data = requests.get(img_url).content
                st.session_state.generated_image = img_data
                
                # [단계 3] 전처리
                st.write("⚙️ 전처리(이진화) 중...")
                processed_data = process_image_to_sketch(img_data)
                
                if processed_data:
                    st.session_state.processed_image = processed_data
                    st.success("✅ 모든 처리 완료!")
                else:
                    st.error("🚨 전처리 과정에서 실패했습니다.")
            else:
                st.error("🚨 DALL-E가 이미지를 생성하지 못했습니다. (터미널 확인 요망)")

# ==========================================
# 🖼️ 결과 확인
# ==========================================
if 'generated_image' in st.session_state and 'processed_image' in st.session_state:
    col1, col2 = st.columns(2)
    with col1:
        st.image(st.session_state.generated_image, caption="AI 원본")
    with col2:
        st.image(st.session_state.processed_image, caption="플로터용 전처리")
        
    st.divider()
    
    if st.button("⚙️ G-code 변환 (Potrace)"):
        gcode_result = image_to_gcode(st.session_state.processed_image)
        
        if "Error" in gcode_result:
            st.error(gcode_result)
        else:
            st.success("G-code 생성 성공!")
            st.text_area("G-code 결과", gcode_result[:500] + "\n...", height=150)
            st.download_button("G-code 다운로드", gcode_result, "plot.gcode")
