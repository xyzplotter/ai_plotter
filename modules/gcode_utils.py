import cv2
import numpy as np

# ==========================================
# ⚙️ [설정] 웹 서버용 변환 상수
# ==========================================
TARGET_WIDTH_MM = 100.0   
OFFSET_X = 75.0           
OFFSET_Y = -75.0          

FEED_RATE_MOVE = 2000     
FEED_RATE_DRAW = 3500     

# 1.5mm 미만 잡티 제거 (점묘화 방지)
MIN_LINE_LENGTH_MM = 1.5  

# 🔥 [핵심] 데이터 용접 거리 (3.0mm 이내면 강제 연결)
WELD_DISTANCE_MM = 2.0    
# ==========================================

# 1. 거리순 정렬 함수
def sort_contours_by_distance(contours):
    if not contours: return []
    sorted_contours = []
    unvisited = list(contours)
    current_pos = np.array([0, 0])

    while unvisited:
        best_index = -1
        min_dist = float('inf')
        should_reverse = False

        for i, cnt in enumerate(unvisited):
            start_pt = cnt[0][0]
            end_pt = cnt[-1][0]
            dist_to_start = np.linalg.norm(current_pos - start_pt)
            dist_to_end = np.linalg.norm(current_pos - end_pt)

            if dist_to_start < min_dist:
                min_dist = dist_to_start
                best_index = i
                should_reverse = False
            if dist_to_end < min_dist:
                min_dist = dist_to_end
                best_index = i
                should_reverse = True

        best_cnt = unvisited.pop(best_index)
        if should_reverse:
            best_cnt = best_cnt[::-1]
        sorted_contours.append(best_cnt)
        current_pos = best_cnt[-1][0]
    return sorted_contours

# 2. 이미지 전처리 (슈퍼 글루: 살찌우기 + 뼈대화)
def process_image_super_glue(image):
    _, binary = cv2.threshold(image, 127, 255, cv2.THRESH_BINARY_INV)
    
    # 0단계: 미세 노이즈 살짝 제거
    kernel_noise = np.ones((2,2), np.uint8) 
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_noise)

    # 1단계: 선 살찌우기 (Dilation) - 끊김 방지
    kernel = np.ones((3,3), np.uint8)
    fat_lines = cv2.dilate(binary, kernel, iterations=2)
    fat_lines = cv2.morphologyEx(fat_lines, cv2.MORPH_CLOSE, kernel)
    
    # 2단계: 뼈대화 (Skeletonize)
    skeleton = np.zeros(fat_lines.shape, np.uint8)
    element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    
    temp_img = fat_lines.copy()
    while True:
        eroded = cv2.erode(temp_img, element)
        temp = cv2.dilate(eroded, element)
        temp = cv2.subtract(temp_img, temp)
        skeleton = cv2.bitwise_or(skeleton, temp)
        temp_img = eroded.copy()
        if cv2.countNonZero(temp_img) == 0: break
    
    # 3단계: 뼈대 다듬기
    skeleton = cv2.morphologyEx(skeleton, cv2.MORPH_CLOSE, kernel)
    
    return skeleton

# 3. 🔥 [핵심] 좌표 데이터 용접 (Geometry Welding)
def weld_contours(contours, scale):
    if not contours: return []
    
    lines = [cnt for cnt in contours]
    merged_lines = []
    
    while lines:
        current_line = lines.pop(0)
        
        while True:
            found_neighbor = False
            current_end = current_line[-1][0]
            
            best_idx = -1
            min_dist = float('inf')
            match_mode = 0 
            
            for i, target in enumerate(lines):
                target_start = target[0][0]
                target_end = target[-1][0]
                
                d1 = np.linalg.norm(current_end - target_start)
                d2 = np.linalg.norm(current_end - target_end)
                
                dist_mm_1 = d1 * scale
                dist_mm_2 = d2 * scale
                
                if dist_mm_1 < WELD_DISTANCE_MM and dist_mm_1 < min_dist:
                    min_dist = dist_mm_1
                    best_idx = i
                    match_mode = 1 # 정방향
                
                elif dist_mm_2 < WELD_DISTANCE_MM and dist_mm_2 < min_dist:
                    min_dist = dist_mm_2
                    best_idx = i
                    match_mode = 2 # 역방향
            
            if best_idx != -1:
                target = lines.pop(best_idx)
                if match_mode == 1: 
                    current_line = np.vstack((current_line, target))
                else: 
                    current_line = np.vstack((current_line, target[::-1]))
                found_neighbor = True 
            
            if not found_neighbor:
                break
        
        merged_lines.append(current_line)
        
    return merged_lines

# ==========================================
# 🚀 [메인] 웹 요청 처리 함수 (image_bytes -> G-code String)
# ==========================================
def image_to_gcode(image_bytes):
    try:
        # 1. 이미지 디코딩
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        if image is None: return "Error: 이미지 로드 실패"

        # 2. 전처리 (블러 + 슈퍼 글루)
        blurred = cv2.GaussianBlur(image, (5, 5), 0)
        skeleton = process_image_super_glue(blurred)
        
        # 3. 외곽선 찾기
        contours, _ = cv2.findContours(skeleton, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours: return "Error: 외곽선 없음 (이미지가 너무 흐리거나 비어있음)"

        # 스케일 계산
        height, width = image.shape
        scale = TARGET_WIDTH_MM / width

        # 4. 1차 필터링 (길이 체크)
        filtered_contours = []
        for cnt in contours:
            length_px = cv2.arcLength(cnt, False)
            length_mm = length_px * scale
            
            # 1.5mm 이상만 살림 (점묘화 방지)
            if length_mm >= MIN_LINE_LENGTH_MM:
                epsilon = 0.002 * length_px
                approx = cv2.approxPolyDP(cnt, epsilon, False)
                filtered_contours.append(approx)

        # 5. 🔥 [핵심] 데이터 용접 (Welding)
        # 끊어진 선들을 3mm 이내라면 강제로 이어 붙임
        welded_contours = weld_contours(filtered_contours, scale)

        # 6. 정렬 (가까운 순서대로)
        sorted_cnts = sort_contours_by_distance(welded_contours)

        # 7. G-code 생성
        gcode = []
        gcode.append("G21")      
        gcode.append("G90")      
        gcode.append("G92 X0 Y0") 
        gcode.append("M3 S1000") 
        gcode.append(f"G1 F{FEED_RATE_DRAW}") 
        gcode.append("M5")       
        gcode.append(f"G0 F{FEED_RATE_MOVE} X{OFFSET_X:.2f} Y{OFFSET_Y:.2f}")

        for cnt in sorted_cnts:
            if len(cnt) < 2: continue

            start_point = cnt[0][0]
            start_x = (start_point[0] * scale) + OFFSET_X
            start_y = (-start_point[1] * scale) + OFFSET_Y 
            
            # 용접된 덩어리 단위로 움직임
            gcode.append("M5")
            gcode.append(f"G0 X{start_x:.2f} Y{start_y:.2f}")
            gcode.append("M3")
            
            for point in cnt[1:]:
                x = (point[0][0] * scale) + OFFSET_X
                y = (-point[0][1] * scale) + OFFSET_Y
                gcode.append(f"G1 X{x:.2f} Y{y:.2f}")

            gcode.append("M5")

        gcode.append("G0 X0 Y0")
        
        # 문자열로 반환 (웹 전송용)
        return "\n".join(gcode)

    except Exception as e:
        return f"Error: 변환 중 오류 발생 - {str(e)}"
