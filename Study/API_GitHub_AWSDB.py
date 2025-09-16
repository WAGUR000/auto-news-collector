import boto3
import os
import requests
import pendulum
import google.generativeai as genai
from urllib.parse import quote, urlparse
import json
import argparse
import uuid
from decimal import Decimal
from dotenv import load_dotenv
from boto3.dynamodb.conditions import Key
from sentence_transformers import SentenceTransformer, util
import torch
from news_organization_lists import NEWS_OUTLET_MAP

# --- 설정값 ---
DYNAMODB_TABLE_NAME = 'News_Data_v1'
GEMINI_MODEL_NAME = 'gemini-2.5-flash'
AWS_REGION = 'ap-northeast-2'
CLUSTERING_THRESHOLD = 0.85 # 군집화 유사도 임계값 (0.0 ~ 1.0)

# GitHub Actions 환경에서는 키를 직접 넣지 않아도 알아서 인증됩니다.
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
table = dynamodb.Table(DYNAMODB_TABLE_NAME)

# SentenceTransformer 모델 로드 (스크립트 시작 시 한 번만 로드)
# GPU가 있으면 'cuda', 없으면 'cpu'를 자동으로 사용합니다.
device = 'cuda' if torch.cuda.is_available() else 'cpu'
sbert_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2', device=device)

def save_data(articles_list):
    """DynamoDB의 BatchWriter를 사용해 여러 항목을 한번에 효율적으로 저장합니다."""
    try:
        with table.batch_writer() as batch:
            for item in articles_list:
                # DynamoDB는 float 타입을 지원하지 않으므로 Decimal로 변환합니다.
                # json.dumps와 loads를 이용하면 중첩된 구조의 float도 모두 Decimal로 쉽게 변환할 수 있습니다.
                item_decimal = json.loads(json.dumps(item), parse_float=Decimal)
                batch.put_item(Item=item_decimal)
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

def get_recent_articles(limit=100):
    """DynamoDB에서 최신 기사 'limit'개를 가져옵니다."""
    try:
        today_str = pendulum.now('Asia/Seoul').to_date_string()
        yesterday_str = pendulum.now('Asia/Seoul').subtract(days=1).to_date_string()

        # 오늘 기사 조회 (최신순)
        response_today = table.query(
            KeyConditionExpression=Key('PK').eq(today_str),
            ScanIndexForward=False
        )
        items = response_today.get('Items', [])

        # 오늘 기사가 부족하면 어제 기사도 조회
        if len(items) < limit:
            response_yesterday = table.query(
                KeyConditionExpression=Key('PK').eq(yesterday_str),
                ScanIndexForward=False
            )
            items.extend(response_yesterday.get('Items', []))

        # 모든 기사를 SK(시간) 기준으로 최신순 정렬 후 limit만큼 반환
        items.sort(key=lambda x: x.get('SK', ''), reverse=True)
        return items[:limit]
    except Exception as e:
        print(f"DynamoDB에서 최근 기사를 가져오는 중 에러 발생: {e}")
        return []

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
        print("--- 🧪 테스트 모드로 실행합니다. (신규 2개 + 기존 2개) ---")
        display_count = 2
        batch_size = 2
        recent_articles_limit = 2
    else:
        display_count = 100
        batch_size = 10
        recent_articles_limit = 100

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

    # 5. DB에서 최신 기사 가져오기 (군집화 비교 대상)
    print("--- 💾 DynamoDB에서 군집화 비교를 위한 최신 기사를 가져옵니다. ---")
    recent_db_articles = get_recent_articles(limit=recent_articles_limit)
    print(f"--- {len(recent_db_articles)}개의 기존 기사를 가져왔습니다. ---")

    # 5. 뉴스 군집화 (Clustering)
    # 새로 수집된 기사와 DB의 최신 기사를 합쳐서 군집화 수행
    all_articles_for_clustering = recent_db_articles + processed_articles_for_db

    if all_articles_for_clustering:
        print(f"--- 📰 뉴스 군집화를 시작합니다. (총 {len(all_articles_for_clustering)}개 기사, 임계값: {CLUSTERING_THRESHOLD}) ---")

        # 각 기사의 제목과 설명을 합쳐서 벡터로 변환할 문장 리스트 생성
        corpus = [f"{article['title']}. {article.get('description', '')}" for article in all_articles_for_clustering]

        # SBERT 모델을 사용하여 문장들을 임베딩(벡터화)
        embeddings = sbert_model.encode(corpus, convert_to_tensor=True, show_progress_bar=False)

        # 코사인 유사도 기반으로 임계값 이상의 유사도를 가진 기사 군집 탐색
        clusters = util.community_detection(embeddings, min_community_size=1, threshold=CLUSTERING_THRESHOLD)

        cluster_id_map = {}
        representative_map = {} # 대표 기사 인덱스를 기록하기 위한 맵

        # 각 군집에 대해 고유 ID 부여 및 대표 기사 설정
        for cluster in clusters:
            # 군집의 대표 ID로 짧고 고유한 UUID를 생성합니다.
            cluster_id = uuid.uuid4().hex

            # 군집의 첫 번째 기사를 대표로 지정합니다.
            representative_idx = cluster[0]
            representative_map[representative_idx] = 1

            for article_idx in cluster:
                # 맵에 '기사 인덱스' -> 'UUID clusterId' 저장
                cluster_id_map[article_idx] = cluster_id

        # 새로 수집된 기사들에 대해서만 cluster_id와 is_representative를 할당
        start_index_for_new_articles = len(recent_db_articles)
        for i, article in enumerate(processed_articles_for_db):
            # 전체 목록에서의 인덱스 계산
            combined_list_index = start_index_for_new_articles + i

            # 해당 인덱스의 기사가 속한 군집의 ID를 가져옴
            cluster_id = cluster_id_map.get(combined_list_index)

            if cluster_id:
                article['clusterId'] = cluster_id
                # 대표 기사 맵을 확인하여 대표 여부를 설정합니다.
                article['is_representative'] = 1 if representative_map.get(combined_list_index) else 0
            else:
                # 군집에 속하지 않은 경우, 자기 자신을 대표로 설정하고 새로운 UUID를 부여합니다.
                article['clusterId'] = uuid.uuid4().hex
                article['is_representative'] = 1
        print(f"--- 군집화 완료. 총 {len(clusters)}개의 군집을 찾았습니다. ---")

    # 6. 최종 데이터 저장
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