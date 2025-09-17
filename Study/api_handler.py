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
GEMINI_MODEL_NAME = 'gemini-2.5-flash' # 모델 설정
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
               f"""아래는 뉴스 기사 목록입니다. 각 기사에 대해 `temp_id`, 주요 토픽, 감정, 대분류, 소분류, 중요도를 추출해 JSON 리스트로 반환하세요.
                 반드시 입력된 `temp_id`를 그대로 유지해야 하고, 아래의 출력 형식과 규칙을 반드시 지켜주세요.
                  ### 필수 규칙: 대분류 선택
                   아래에 제시된 8개의 `대분류` 중 가장 적합한 하나를 선택하여 `category1` 값으로 지정하세요.
                    - 정치
                    - 경제
                    - 사회
                    - IT/과학
                    - 문화/생활
                    - 연예
                    - 스포츠
                    - 국제
            입력:
            {json.dumps(articles_for_prompt, ensure_ascii=False, indent=2)}
            
            출력 형식:
            [
              {{
                "temp_id": "article_0",
                "topic": "주요 토픽",
                "sentiment": 0.0(부정)~5.0(중립)~10.0(긍정) 사이의 실수 (float형식, 소수점 첫째자리까지)",
                "category1": "대분류",
                "category2": "소분류",
                "importance": 1~10 사이의 정수 (1: 매우 낮음, 10: 매우 높음, int형식)
              }},
              ...
            ]
            """
        )
        
    try:
        response = model.generate_content(prompt)
        json_str = response.text.strip('`').strip('json').strip()
        try:
            # 응답에서 JSON 파싱
            gemini_result = json.loads(json_str)
            return gemini_result
        except json.JSONDecodeError as e:
            print(f"Gemini 응답 JSON 파싱 에러: {e}")
            print(f"원본 응답 텍스트: {json_str}")

    except Exception as e:
        print(f"Gemini API 호출 또는 응답 처리 중 에러 발생: {e}")
        