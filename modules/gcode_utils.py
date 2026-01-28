import subprocess
import os
import sys
from svgpathtools import svg2paths

def image_to_gcode(image_bytes, output_filename="plot.gcode"):
    """
    [최종 통합본]
    1. BMP 저장 (Potrace 호환)
    2. Potrace 실행 (절대경로)
    3. SVG 파싱
    4. 크기 80mm 안전 축소
    5. CoreXY (X+Y, X-Y) 좌표 변환 적용 ✨
    """
    temp_bmp = "temp_input.bmp"
    temp_svg = "temp_output.svg"
    
    # 1. BMP 파일 저장
    with open(temp_bmp, "wb") as f:
        f.write(image_bytes)

    # 2. Potrace 실행 (윈도우 절대경로 방어)
    if sys.platform == "win32":
        potrace_path = os.path.abspath("potrace.exe")
        if not os.path.exists(potrace_path):
             return "Error: 'potrace.exe' 파일이 없습니다."
        command = [potrace_path, temp_bmp, "-s", "-o", temp_svg]
    else:
        command = ["potrace", temp_bmp, "-s", "-o", temp_svg]

    try:
        subprocess.run(command, check=True)
    except Exception as e:
        return f"Error: Potrace 실행 실패 - {e}"

    # 3. SVG 파싱
    try:
        paths, _ = svg2paths(temp_svg)
    except Exception as e:
        return f"SVG 파싱 에러: {e}"
    
    if not paths: return "Error: 변환된 선이 없습니다."

    # 4. 크기 조절 (80mm = 8cm)
    all_points = []
    for path in paths:
        for i in range(10): 
            all_points.append(path.point(i/10))
    
    if not all_points: return "Error: 점 데이터가 없습니다."

    min_x = min([p.real for p in all_points])
    min_y = min([p.imag for p in all_points])
    
    # 가로폭 계산
    current_width = max([p.real for p in all_points]) - min_x

    # [설정] 출력 크기 80mm
    TARGET_WIDTH_MM = 80.0  
    
    if current_width == 0: scale = 1.0
    else: scale = TARGET_WIDTH_MM / current_width

    # ==========================================
    # 🔄 CoreXY 좌표 변환 함수
    # 아두이노 로직(HIGH, HIGH / HIGH, LOW)과 완벽 일치함
    # ==========================================
    def to_corexy(x, y):
        motor_a = x + y
        motor_b = x - y
        return motor_a, motor_b

    # 5. G-code 생성
    gcode = []
    gcode.append("G21")      # 단위: mm
    gcode.append("G90")      # 절대 좌표
    gcode.append("M3 S1000") # 펜 서보 준비 (아두이노가 읽어서 처리해야 함)
    gcode.append("G1 F3000") # 속도
    
    for path in paths:
        if path.length() < 2: continue # 노이즈 제거
        
        # 시작점으로 이동 (펜 들고 M5)
        start = path.start
        
        # 1) 원본 좌표 (0점 조절 + 스케일링)
        sx_raw = (start.real - min_x) * scale
        sy_raw = (start.imag - min_y) * scale
        
        # 2) CoreXY 변환 (섞기)
        sx, sy = to_corexy(sx_raw, sy_raw)
        
        gcode.append("M5") # 펜 들기
        gcode.append(f"G0 X{sx:.2f} Y{sy:.2f}") # 이동
        gcode.append("M3") # 펜 내리기
        
        # 곡선 그리기
        steps = 10
        for i in range(1, steps + 1):
            p = path.point(i / steps)
            
            # 1) 원본 좌표
            px_raw = (p.real - min_x) * scale
            py_raw = (p.imag - min_y) * scale
            
            # 2) CoreXY 변환
            px, py = to_corexy(px_raw, py_raw)
            
            gcode.append(f"G1 X{px:.2f} Y{py:.2f}")
    
    gcode.append("M5")       # 펜 들기
    gcode.append("G0 X0 Y0") # 원점 복귀
    
    return "\n".join(gcode)