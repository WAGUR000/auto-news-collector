import os
import json
import time
import requests
from urllib.parse import quote
from dotenv import load_dotenv
from openai import OpenAI  # google.generativeai 대신 사용
from time import sleep

load_dotenv() # .env 파일에서 환경 변수 로드. 없을경우 넘어감 

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET")

if not all([GROQ_API_KEY, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET]):
    print("에러: 필요한 환경변수(GROQ_API_KEY, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET)가 설정되지 않았습니다.")
    exit(1)

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY
)
GROQ_MODEL_NAME = "llama-3.1-8b-instant"

import requests
from urllib.parse import quote
import time # API 호출 간격을 위해 추가

def naver_api_request(display_count=150):
    keyword = "뉴스"
    enc_keyword = quote(keyword)
    headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET}
    
    all_articles = [] # 결과를 모을 리스트

    # Naver API는 start 값이 최대 1000까지만 가능하므로, 최대 1000건까지만 수집 가능하도록 제한
    if display_count > 1000:
        print("경고: 네이버 API 정책상 최대 1000건까지만 조회 가능합니다. 1000건으로 조정합니다.")
        display_count = 1000

    try:
        # 1부터 display_count까지 100단위로 건너뛰며 반복 (예: 1, 101, 201...)
        for start_index in range(1, display_count + 1, 100):
            
            # 이번 요청에 필요한 개수 계산 (남은 개수와 100 중 작은 값 선택)
            # 예: 150개 요청 시 -> 첫 번째 루프: 100, 두 번째 루프: 50
            query_display = min(100, display_count - len(all_articles))
            
            url = f"https://openapi.naver.com/v1/search/news.json?query={enc_keyword}&display={query_display}&start={start_index}&sort=date"
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            news_data = response.json()
            items = news_data.get("items", [])
            
            # 결과 리스트에 추가
            all_articles.extend(items)
            
            # 검색 결과가 요청한 것보다 적으면 조기 종료 (예: 검색 결과가 총 5개뿐인 경우)
            if len(items) < query_display:
                break
                
            # 연속 호출 시 네이버 서버 부하 방지 및 차단 예방을 위한 아주 짧은 대기
            time.sleep(0.1)

        return all_articles

    except requests.exceptions.RequestException as e:
        print(f"네이버 뉴스 API 호출 중 에러 발생: {e}")
        # 에러 발생 시 부분 수집된 데이터라도 반환할지, 아니면 종료할지 결정 필요
        # 여기서는 기존 로직대로 종료 처리
        exit(1)
  
import json
import re

def groq_api_request(articles):
    # 1. 전처리
    articles_for_prompt = [
        {
            "temp_id": item.get('temp_id', str(idx)), 
            "title": item.get("title", "").replace("<b>", "").replace("</b>", ""),
            "description": item.get("description", "").replace("<b>", "").replace("</b>", "")
        }
        for idx, item in enumerate(articles)
    ]

    # 2. 시스템 프롬프트 (temp_id 복사 강조)
    system_prompt = """
    You are an expert news editor. Your task is to generate concise "headline-style" summaries (topics) for news articles.
    
    [CRITICAL RULES - OUTPUT FORMAT]
    1. Output MUST be a single, valid JSON object starting with '{'.
    2. The JSON object must contain a single key "reviews" with an array of objects.
    3. Each object MUST have 'temp_id' (copied exactly) and 'topic'.
    4. NO text outside the JSON object.

    [CRITICAL RULES - TOPIC STYLE]
    1. Use **Korean**.
    2. Use **Noun Phrase (명사형 종결)** or **Headline Style**.
       - BAD: "삼성전자가 실적을 발표했다." (Full sentence)
       - GOOD: "삼성전자, 3분기 실적 발표" (Noun phrase)
       - GOOD: "비트코인 급등, 사상 최고가 경신" (Headline style)
    3. Keep it concise (under 50 characters if possible).
    """

    user_prompt = f"""
    Analyze the news list below and return a JSON object with headline-style topics.

    Input:
    {json.dumps(articles_for_prompt, ensure_ascii=False, indent=2)}
    """
    try:
        completion = client.chat.completions.create(
            model=GROQ_MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
        )

        response_content = completion.choices[0].message.content
        
        # 3. 강화된 JSON 추출 및 파싱
        json_str = None
        
        # 시도 1: 마크다운 코드 블록 (```json ... ```) 에서 JSON 추출
        match = re.search(r'```json\s*(\{.*?\})\s*```', response_content, re.DOTALL)
        if match:
            json_str = match.group(1)
        else:
            # 시도 2: 응답 내용 전체에서 { ... } 패턴 찾기
            match = re.search(r'\{.*\}', response_content, re.DOTALL)
            if match:
                json_str = match.group()

        if not json_str:
            print("--- Groq API 응답에서 JSON 객체를 찾을 수 없습니다. ---")
            print("API 응답 내용:", response_content)
            return []

        try:
            result_json = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"--- JSON 파싱 에러: {e} ---")
            print("파싱 시도한 문자열:", json_str)
            return []

        # 4. 구조 확인 및 반환
        if isinstance(result_json, dict) and "reviews" in result_json:
            # 반환 전, 모든 리뷰에 temp_id가 있는지 추가로 확인
            reviews = result_json.get("reviews", [])
            if all('temp_id' in item for item in reviews):
                print(f"--- ✅ Groq API에서 {len(reviews)}개의 토픽을 성공적으로 생성했습니다. (temp_id 포함) ---")
                sleep(5)
                return reviews
            else:
                print("--- Groq API 응답의 일부 항목에 'temp_id'가 누락되었습니다. ---")
                print("전체 응답:", reviews)
                # temp_id가 없는 항목을 필터링하고 반환할지, 아니면 빈 리스트를 반환할지 결정
                # 여기서는 문제가 있는 배치를 아예 건너뛰도록 빈 리스트 반환
                return []
        else:
            print("--- Groq API 응답의 JSON 구조가 예상과 다릅니다. ---")
            print("파싱된 JSON:", result_json)
            return []

    except Exception as e:
        # ⚠️ 예외 발생 시 처리 (토큰 초과, 컨텍스트 길이 초과 등)
        print(f"\n[Warning] API 호출 실패 (사유: {e})")
        print(">> 🚨 토큰 제한 또는 에러 발생으로 인해 '제목'을 '토픽'으로 대체합니다.")

        # 2. [Fallback 로직] 제목을 토픽으로 매핑하여 반환
        fallback_results = []
        for article in articles:
            fallback_results.append({
                'temp_id': article.get('temp_id'),  # ID 유지
                'topic': article.get('title', '제목 없음')  # 제목을 토픽으로 사용
            })
            
        return fallback_results