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

def gemini_api_request(articles):
    news_schema = {
        "type": "ARRAY",
        "items": {
            "type": "OBJECT",
            "properties": {
                "temp_id": {"type": "STRING"},
                "topic": {"type": "STRING"},
                "keywords": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"}
                },
                "sentiment": {"type": "NUMBER"},
                "category1": {
                    "type": "STRING", 
                    "enum": ["정치", "경제", "사회", "IT/과학", "문화/생활", "연예", "스포츠", "국제"]
                },
                "category2": {"type": "STRING"},
                "importance": {"type": "INTEGER"}
            },
            "required": ["temp_id", "topic", "keywords", "sentiment", "category1", "category2", "importance"]
        }
    }
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
             6. **importance**: 기사 중요도를 0~10 사이의 정수로 평가 (0=매우낮음, 5=보통,10=매우높음). 사회적 영향력, 이슈성 등을 고려
             * **0점 (데이터로서 가치 없음)**:
            - **[포토], [화보]** 등 텍스트 없이 사진만 있는 기사.
            - 날씨 예보(태풍/지진 등 제외), 부고 알림
            - 기사 내용이 없거나 제목만 있는 오류성 데이터.

            * **1~3점 (홍보/가십/단순 기록 - 큰 의미는 없음 )**:
            - **지자체/기관 소식**: 단순 수상, 기부, 자선행사, MOU 체결, 지역 축제 알림.
            - **기업 PR**: 신제품 출시, 이벤트 프로모션, 사내 행사.
            - **연예/가십**: 앨범/음원 발표, 연예인 SNS/셀카 기사, 공항 패션, 단순 근황.

            * **4~5점 (일반 뉴스 - 보통)**:
            - 특정 업계의 일반적인 동향, 기업 실적 발표.
            - 사회적 논의가 필요한 소규모 사건/사고.
            - 대중의 관심이 있는 생활 정보나 문화 뉴스.

            * **6~8점 (주요 이슈 / 중요)**:
            - **사회적 파장**: 법안 발의/통과, 물가 상승, 부동산 정책 변화.
            - **주목할 사건**: 인명 피해가 있는 사고, 유명 정치인의 주요 행보.
            - 대중의 이목이 쏠리는 논란이나 이슈.

            * **9~10점 (국가적/역사적 이슈 / 매우 중요)**:
            - **경제 충격**: 환율 급등(예: 1480원 돌파), 기준금리 대폭 변경, 주가 폭락/폭등.
            - **국가 재난**: 전쟁(국내외 전쟁양상 변화나 전쟁발발), 대형 참사(대규모 화재, 지진, 태풍, 쓰나미 등), 전염병 대유행, 대통령 탄핵/당선.
            - 역사에 기록될 만한 중대한 발견이나 사건.
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
        response = model.generate_content(prompt,generation_config={
            "response_mime_type": "application/json",  
            "response_schema": news_schema,
            "temperature": 0.3,
        })
        
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
        