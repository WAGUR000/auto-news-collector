import os
import json
import time
import requests
from urllib.parse import quote
from dotenv import load_dotenv
from openai import OpenAI  # google.generativeai 대신 사용

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
GROQ_MODEL_NAME = "llama-3.3-70b-versatile"

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
  
def groq_api_request(articles):
    # 전처리: 불필요한 태그 제거 및 데이터 경량화
    articles_for_prompt = [
        {
            "temp_id": item.get('temp_id', str(idx)), # temp_id가 없으면 인덱스로 대체 방어 로직
            "title": item.get("title", "").replace("<b>", "").replace("</b>", ""),
            "description": item.get("description", "").replace("<b>", "").replace("</b>", "")
        }
        for idx, item in enumerate(articles)
    ]

    # 프롬프트: JSON Mode 사용을 위해 출력 형식을 명확히 지정
    system_prompt = """
    당신은 숙련된 데이터 분석가입니다. 
    제공된 뉴스 기사 목록을 분석하여 지정된 JSON 형식으로 반환해야 합니다.
    반드시 JSON 포맷만 출력하세요.
    """

    user_prompt = f"""
    아래 뉴스 기사 목록을 분석하여 JSON 객체를 반환하세요.
    반환할 JSON은 반드시 {{"reviews": [...]}} 형태여야 합니다.

    ### 분석 목표 (각 기사별 항목)
    1. **topic**: 한 문장 요약 (예: "배우 이순재 별세")
    2. **keywords**: 핵심 단어 3~5개 리스트
    3. **sentiment**: 0.0(부정) ~ 10.0(긍정) 실수
    4. **category1**: [정치, 경제, 사회, IT/과학, 문화/생활, 연예, 스포츠, 국제] 중 택 1
    5. **category2**: 세부 카테고리 (예: 경제-금융시장, 스포츠-축구, 문화/생활-영화 등)
    6. **importance**: 0(무가치)~10(매우중요) 정수
            * **0점 (데이터로서 가치 없음)**:
            - **[포토], [화보]** 등 텍스트 없이 사진만 있는 기사.
            - 날씨 예보(태풍/지진 등 제외), 부고 알림
            - 기사 내용이 없거나 제목만 있는 오류성 데이터.

            * **1~3점 (홍보/가십/단순 기록 - 큰 의미는 없음 )**:
            - **연예/방송**: **드라마/영화 캐스팅, 출연 확정, 티저/예고편 공개, 앨범 발매, 시청률 기사.** (유명 배우가 나와도 단순 작품 활동은 여기에 포함)
            - **가십**: 연예인 SNS, 공항 패션, 단순 근황, 먹방/여행 예능 리뷰.
            - **단순 홍보**: 기업/지자체의 수상, MOU 체결, 단순 행사 알림.

            * **4~5점 (일반 뉴스 - 보통)**:
            - 특정 업계의 일반적인 동향, 기업 실적 발표.
            - 사회적 논의가 필요한 소규모 사건/사고.
            - 대중의 관심이 있는 생활 정보나 문화 뉴스.

            * **6~8점 (주요 이슈 / 중요)**:
            - **사회적 파장**: 법안 발의/통과, 물가 상승, 부동산 정책 변화.
            - **주목할 사건**: 인명 피해가 있는 사고, 유명인의 사망, 마약/음주운전 등 범죄 연루, 은퇴, 그룹 해체.(사회적 파장이 있는 경우)
            - 대중의 이목이 쏠리는 논란이나 이슈.

            * **9~10점 (국가적/역사적 이슈 / 매우 중요)**:
            - **경제 충격**: 환율 급등(예: 1480원 돌파), 기준금리 대폭 변경, 주가 폭락/폭등.
            - **국가 재난**: 전쟁(국내외 전쟁양상 변화나 전쟁발발), 대형 참사(대규모 화재, 지진, 태풍, 쓰나미 등), 전염병 대유행, 대통령 탄핵/당선.
            - 역사에 기록될 만한 중대한 발견이나 사건.


    ### 입력 데이터
    {json.dumps(articles_for_prompt, ensure_ascii=False, indent=2)}

    ### 필수 출력 형식
    {{
        "reviews": [
            {{
                "temp_id": "입력된 ID 유지",
                "topic": "요약문",
                "keywords": ["키워드1", "키워드2"],
                "sentiment": 5.0,
                "category1": "경제",
                "category2": "금융",
                "importance": 5
            }},
            ...
        ]
    }}
    """

    try:
        completion = client.chat.completions.create(
            model=GROQ_MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"} # Groq JSON 모드 활성화
        )

        # 응답 파싱
        response_content = completion.choices[0].message.content
        result_json = json.loads(response_content)
        
        # "reviews" 키 안의 리스트를 반환
        return result_json.get("reviews", [])

    except Exception as e:
        print(f"Groq API 호출 중 에러 발생: {e}")
        # 디버깅을 위해 실패 시 원본 응답을 찍어볼 수 있음
        # print(completion.choices[0].message.content) 
        return []

# --- 실행 예시 (테스트용) ---
if __name__ == "__main__":
    # 1. 뉴스 수집
    print("뉴스 수집 시작...")
    news_list = naver_api_request(display_count=5) # 테스트로 5개만
    
    # temp_id 부여 (기존 로직에 있다고 가정)
    for idx, news in enumerate(news_list):
        news['temp_id'] = f"news_{idx}"

    # 2. AI 분석
    print(f"Groq 분석 시작 ({len(news_list)}건)...")
    analyzed_data = groq_api_request(news_list)
    
    # 3. 결과 출력
    print(json.dumps(analyzed_data, ensure_ascii=False, indent=2))