import cv2
import numpy as np

def process_image_to_sketch(image_bytes):
    """
    [최종] 512px 리사이징 + 뼈대(Skeleton) 추출 + 안전 여백(Padding) 추가
    """
    # 1. 이미지 읽기
    file_bytes = np.asarray(bytearray(image_bytes), dtype=np.uint8)
    image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    
    if image is None: return None

    # 2. 리사이징 (512px)
    image = cv2.resize(image, (512, 512), interpolation=cv2.INTER_AREA)

    # 3. 흑백 변환
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # 4. 이진화
    _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)

    # 5. 세선화 (Skeletonization) - 뼈대만 남기기
    skeleton = np.zeros(binary.shape, np.uint8)
    element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    
    while True:
        eroded = cv2.erode(binary, element)
        temp = cv2.dilate(eroded, element)
        temp = cv2.subtract(binary, temp)
        skeleton = cv2.bitwise_or(skeleton, temp)
        binary = eroded.copy()
        
        if cv2.countNonZero(binary) == 0:
            break
            
    # 6. [NEW] 안전 여백(Padding) 추가 🛡️
    # 상하좌우에 50픽셀씩 흰색(0이 아니라 255여야 하는데 반전 전이라 0) 테두리를 추가
    # 나중에 반전되면 흰색 여백이 됨
    padding_size = 50
    skeleton_with_border = cv2.copyMakeBorder(
        skeleton, 
        padding_size, padding_size, padding_size, padding_size, # 상, 하, 좌, 우
        cv2.BORDER_CONSTANT, 
        value=0 # 검은색(나중에 흰색 됨)으로 채움
    )

    # 7. 색상 반전 (흰 배경, 검은 선)
    result = cv2.bitwise_not(skeleton_with_border)
    
    # 8. BMP 저장
    is_success, buffer = cv2.imencode(".bmp", result)
    
    if not is_success: return None
    return buffer.tobytes()