import boto3
import os
import requests
import pendulum
import google.generativeai as genai
from urllib.parse import quote, urlparse
import json
import argparse
from dotenv import load_dotenv
from news_organization_lists import NEWS_OUTLET_MAP

# --- 설정값 ---
DYNAMODB_TABLE_NAME = 'News_Data_v1'
GEMINI_MODEL_NAME = 'gemini-2.5-flash'
AWS_REGION = 'ap-northeast-2'

# GitHub Actions 환경에서는 키를 직접 넣지 않아도 알아서 인증됩니다.
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
table = dynamodb.Table(DYNAMODB_TABLE_NAME)

def save_data(articles_list):
    """DynamoDB의 BatchWriter를 사용해 여러 항목을 한번에 효율적으로 저장합니다."""
    try:
        with table.batch_writer() as batch:
            for item in articles_list:
                batch.put_item(Item=item)
        print(f"{len(articles_list)}개의 데이터 저장 성공.")
    except Exception as e:
        print(f"에러 발생: {e}")

def chunked(iterable, n):
    """iterable을 n개씩 묶어서 반환"""
    for i in range(0, len(iterable), n):
        yield iterable[i:i + n]

def get_outlet_name(original_link):
    """
    원본 링크에서 도메인을 추출하여 언론사 이름을 반환합니다.
    매핑되지 않은 경우 '기타언론사'를 반환합니다.
    """
    if not original_link:
        return '기타언론사'
    try:
        domain = urlparse(original_link).netloc
        return NEWS_OUTLET_MAP.get(domain, '기타언론사')
    except Exception:
        return '기타언론사'

def main(is_test_mode=False):
    """뉴스 데이터를 수집, 분석하고 DynamoDB에 저장하는 메인 함수"""
    # 로컬 환경의 .env 파일에서 환경 변수를 불러옵니다.
    # GitHub Actions 환경에서는 .env 파일이 없으므로 이 코드는 무시됩니다.
    # 로컬 테스트
    # .\venv\Scripts\activate (CMD, Git Bash로는 불가능)
    # python Study/API_GitHub_AWSDB.py --test (테스트 환경 실행)


    load_dotenv() # .env 파일에서 환경 변수 로드. 없을경우 넘어감

    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID")
    NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET")

    if not all([GEMINI_API_KEY, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET]):
        print("에러: 필요한 환경변수(GEMINI_API_KEY, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET)가 설정되지 않았습니다.")
        exit(1)

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL_NAME)

    # 테스트 모드일 경우 API 호출량과 배치 크기를 줄입니다.
    if is_test_mode:
        print("--- 🧪 테스트 모드로 실행합니다. (display=2, batch_size=2) ---")
        display_count = 2
        batch_size = 2
    else:
        display_count = 100
        batch_size = 10

    # 1. 네이버 뉴스 API 호출
    keyword = "뉴스"
    enc_keyword = quote(keyword)
    url = f"https://openapi.naver.com/v1/search/news.json?query={enc_keyword}&display={display_count}&start=1&sort=date"
    headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        news_data = response.json()
        raw_articles = news_data.get("items", [])
    except requests.exceptions.RequestException as e:
        print(f"네이버 뉴스 API 호출 중 에러 발생: {e}")
        exit(1)

    # 2. 임시 라벨 추가 및 데이터 준비
    labeled_articles = []
    for i, item in enumerate(raw_articles):
        # 각 기사에 고유한 ID를 부여하여 프롬프트에 포함시킵니다.
        item['temp_id'] = f"article_{i}"
        labeled_articles.append(item)

    processed_articles_for_db = []

    # 3. 뉴스 기사를 배치로 처리하며 Gemini API 호출
    for batch in chunked(labeled_articles, batch_size):
        # API에 보낼 기사 목록을 간결하게 만듭니다.
        articles_for_prompt = [
            {
                "temp_id": item['temp_id'],
                "title": item.get("title", "").replace("<b>", "").replace("</b>", ""),
                "description": item.get("description", "")
            }
            for item in batch
        ]
        
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
            except json.JSONDecodeError as e:
                print(f"Gemini 응답 JSON 파싱 에러: {e}")
                print(f"원본 응답 텍스트: {json_str}")
                continue # 파싱 실패 시 다음 배치로 넘어감
            # 4. Gemini API 응답과 원본 데이터 결합
            gemini_map = {item['temp_id']: item for item in gemini_result}
            
            for item in batch:
                temp_id = item['temp_id']
                if temp_id in gemini_map:
                    gemini_info = gemini_map[temp_id]

                    # 중요도를 안전하게 정수형으로 변환합니다.
                    importance_val = gemini_info.get("importance")
                    try:
                        # 문자열로 된 숫자('7')도 처리하기 위해 int()로 변환합니다.
                        importance = int(importance_val)
                    except (ValueError, TypeError):
                        # 변환 실패 시(예: '높음', None) 기본값 5를 사용하고 로그를 남깁니다.
                        print(f"Warning: 'importance' 값 '{importance_val}'을(를) 정수로 변환할 수 없어 기본값 5를 사용합니다. (temp_id: {temp_id})")
                        importance = 5

                    # 감정을 안전하게 실수형(float)으로 변환합니다.
                    sentiment_val = gemini_info.get("sentiment")
                    try:
                        # 문자열로 된 숫자('7.5')나 정수(5)도 처리하기 위해 float()로 변환합니다.
                        sentiment = float(sentiment_val)
                    except (ValueError, TypeError):
                        # 변환 실패 시(예: '중립', None) 기본값 5.0을 사용하고 로그를 남깁니다.
                        print(f"Warning: 'sentiment' 값 '{sentiment_val}'을(를) 실수로 변환할 수 없어 기본값 5.0을 사용합니다. (temp_id: {temp_id})")
                        sentiment = 5.0
                    
                    pub_date_obj = pendulum.from_format(item.get("pubDate"), 'ddd, DD MMM YYYY HH:mm:ss ZZ', tz='Asia/Seoul')
                    
        
                    pub_date_str1 = pub_date_obj.format('YYYY-MM-DD')
                    link = item.get("link")

                    original_link = item.get("originallink")
                    partition_key = pub_date_str1
                    sort_key = f"{pub_date_obj.to_iso8601_string()}#{link}"




                    # 최종 DynamoDB 저장용 데이터 생성
                    processed_articles_for_db.append({
                        "PK": partition_key, # 파티션 키. 날짜(YYYY-MM-DD)
                        "SK": sort_key, # 정렬 키. ISO 8601 형식의 날짜 + 링크 (유일성 보장)
                        "title": item.get("title", "").replace("<b>", "").replace("</b>", "").replace("&quot;", "\""),
                        "topic": gemini_info.get("topic"),
                        "importance": importance,
                        "sentiment": sentiment,
                        "main_category": gemini_info.get("category1"),
                        "sub_category": gemini_info.get("category2"),
                        "description": item.get("description", "").replace("<b>", "").replace("</b>", "").replace("&quot;", "\""),
                        "pub_date": pub_date_obj.to_iso8601_string(),
                        "originallink": original_link, # 네이버 뉴스링크가 아닌, 뉴스 제공처의 원본 링크
                        "outlet": get_outlet_name(original_link) # originallink 기반으로 언론사 분류
                    })

        except Exception as e:
            print(f"Gemini API 호출 또는 응답 처리 중 에러 발생: {e}")
            continue # 다음 배치로 이동

    # 5. 최종 데이터 저장
    if processed_articles_for_db:
        save_data(processed_articles_for_db)
    else:
        print("처리할 기사가 없습니다.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="뉴스 데이터를 수집하고 분석하여 DynamoDB에 저장합니다.")
    parser.add_argument(
        '--test', 
        action='store_true', 
        help='스크립트를 테스트 모드로 실행합니다. (2개 기사만 처리)'
    )
    args = parser.parse_args()
    main(is_test_mode=args.test)