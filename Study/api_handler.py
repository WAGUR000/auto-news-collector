import os
import google.generativeai as genai
from urllib.parse import quote
import requests
import json
from dotenv import load_dotenv

load_dotenv() # .env 파일에서 환경 변수 로드. 없을경우 넘어감 

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET")

if not all([GEMINI_API_KEY, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET]):
    print("에러: 필요한 환경변수(GEMINI_API_KEY, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET)가 설정되지 않았습니다.")
    exit(1)

genai.configure(api_key=GEMINI_API_KEY)
GEMINI_MODEL_NAME = 'gemini-2.5-flash-lite' # 모델 설정
model = genai.GenerativeModel(GEMINI_MODEL_NAME)

def naver_api_request(display_count=100):
    keyword = "뉴스"
    enc_keyword = quote(keyword)
    url = f"https://openapi.naver.com/v1/search/news.json?query={enc_keyword}&display={display_count}&start=1&sort=date"
    headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        news_data = response.json()
        raw_articles = news_data.get("items", [])
        return raw_articles
    except requests.exceptions.RequestException as e:
        print(f"네이버 뉴스 API 호출 중 에러 발생: {e}")
        exit(1)

def gemini_api_request(articles):
    articles_for_prompt = [
            # API에 보낼 기사 목록을 간결하게 만듭니다.
            {
                "temp_id": item['temp_id'],
                "title": item.get("title", "").replace("<b>", "").replace("</b>", ""),
                "description": item.get("description", "")
            }
            for item in articles]
     
    prompt = (
            f"""아래는 뉴스 기사 목록입니다. 각 기사에 대해 지정된 정보를 추출해 JSON 리스트로 반환하세요.
             
             ### 분석 목표
             1. **topic**: 기사 내용을 한 문장이나 구로 요약 (예: "배우 이순재 별세")
             2. **keywords**: 통계 분석을 위한 **핵심 명사(고유명사, 인물, 기관, 핵심 소재)**를 3~5개 추출 (예: ["이순재", "별세", "원로배우"])
             3. **sentiment**: 기사 감성 점수를 0.0~10.0 사이의 실수로 반환 (0.0=매우부정, 5.0=중립, 10.0=매우긍정)
             4. **category1**: 기사의 대분류 카테고리 (정치, 경제, 사회, IT/과학, 문화/생활, 연예, 스포츠, 국제) 중 하나 선택
             5. **category2**: 기사의 세부 카테고리 (예: 금융시장, 건강, 영화 등)
             6. **importance**: 기사 중요도를 1~10 사이의 정수로 평가 (1=낮음, 10=높음). 사회적 영향력, 이슈성 등을 고려. 연예인 일상,셀카공개 등은 낮음, 주요 정치/경제 뉴스/대형사고등은 높음
             ### 필수 규칙
             1. **ID 유지**: 입력된 `temp_id`를 그대로 반환해야 합니다.
             2. **대분류 선택**: 아래 8개 중 하나를 반드시 선택하여 `category1`에 입력하세요.
                - 정치, 경제, 사회, IT/과학, 문화/생활, 연예, 스포츠, 국제
             3. **JSON 형식 준수**: 응답은 반드시 순수한 JSON 리스트여야 합니다.

            입력 데이터:
            {json.dumps(articles_for_prompt, ensure_ascii=False, indent=2)}
            
            출력 예시 및 형식:
            [
              {{
                "temp_id": "article_0",
                "topic": "기사의 핵심 주제 요약 (구 형태)",
                "keywords": ["핵심단어1", "핵심단어2", "핵심단어3"],
                "sentiment": 0.0,
                "category1": "경제",
                "category2": "금융시장",
                "importance": 7
              }},
              ...
            ]
            
            위 형식을 엄격히 지켜서 JSON 결과만 출력하세요.
            """
        )
        
    try:
        # 모델 설정 (Generation Config를 사용하여 JSON 강제화를 하면 더 안정적입니다)
        response = model.generate_content(prompt)
        
        # 마크다운 코드 블록 제거 및 공백 제거
        json_str = response.text.strip().replace('```json', '').replace('```', '')
        
        try:
            # 응답에서 JSON 파싱
            gemini_result = json.loads(json_str)
            return gemini_result
        except json.JSONDecodeError as e:
            print(f"Gemini 응답 JSON 파싱 에러: {e}")
            print(f"원본 응답 텍스트: {json_str}")

    except Exception as e:
        print(f"Gemini API 호출 또는 응답 처리 중 에러 발생: {e}")
        