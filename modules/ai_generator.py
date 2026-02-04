import openai

def translate_prompt(client, text):
    """
    한글 -> 영어 프롬프트 번역
    (GPT-4o-mini 사용)
    """
    try:
        system_prompt = """You are a translator. 
        Translate the user's input into a simple, descriptive English keyword or phrase suitable for an image prompt. 
        Do not add any style descriptions. Just the subject."""
        
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

def generate_image(client, english_prompt, style_modifier):
    """
    DALL-E 2 이미지 생성
    """
    try:
        # 프롬프트와 스타일 합치기
        full_prompt = f"{english_prompt}{style_modifier}"
        print(f"📌 [Debug] DALL-E 요청 프롬프트: {full_prompt}") 

        response = client.images.generate(
            model="dall-e-2",
            prompt=full_prompt,
            size="1024x1024",
            n=1
        )
        return response.data[0].url
    except Exception as e:
        print(f"🚨 [Error] 이미지 생성 실패: {e}")
        return None
