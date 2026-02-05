import streamlit as st
import gcode_utils  # 우리가 만든 변환기
import serial
import time
import os

# ==========================================
# ⚙️ 설정 (아두이노 포트 확인 필수!)
# ==========================================
SERIAL_PORT = '/dev/ttyACM0'  # 아까 확인한 포트
BAUD_RATE = 115200

# ==========================================
# 🔌 아두이노 전송 함수 (Sender 기능 통합)
# ==========================================
def send_to_arduino(gcode_text):
    try:
        # 1. 아두이노 연결
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        time.sleep(2) # 연결 대기 (중요!)

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
        return True, "출력 완료!"

    except Exception as e:
        return False, f"에러 발생: {str(e)}"

# ==========================================
# 🖥️ 웹 화면 구성
# ==========================================
st.title("🐰 라즈베리 파이 드로잉 봇")

uploaded_file = st.file_uploader("이미지를 올려주세요", type=["png", "jpg", "jpeg"])

if uploaded_file is not None:
    # 1. 이미지 표시
    st.image(uploaded_file, caption='업로드된 이미지', width=300)

    # 2. 변환 및 출력 버튼
    if st.button("🚀 변환하고 바로 그리기!"):
        with st.spinner('G-code 만드는 중...'):
            # 이미지 데이터 읽기
            image_bytes = uploaded_file.getvalue()
            
            # gcode_utils 변환 함수 호출
            gcode_result = gcode_utils.image_to_gcode(image_bytes)

        if "Error" in gcode_result:
            st.error(gcode_result)
        else:
            st.success(f"✅ G-code 생성 완료! (길이: {len(gcode_result)} 글자)")
            
            # 바로 전송 시작
            with st.spinner('아두이노로 전송 중... (기계가 움직입니다!)'):
                success, msg = send_to_arduino(gcode_result)
                
            if success:
                st.balloons()
                st.success(msg)
            else:
                st.error(msg)
