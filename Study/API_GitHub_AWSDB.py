import pendulum
import argparse
from api_handler import naver_api_request, gemini_api_request
from dotenv import load_dotenv
from aws_handler import get_recent_articles, save_data
from clustering_news import cluster_news
from data_processer import chunked, combine_and_format_articles


def main(is_test_mode=False): #is_test_mode: 테스트 모드 여부. 기본값은 False이고 --test를 통해 매개변수 입력시 테스트 모드로 실행
    # 로컬 테스트
    # .\venv\Scripts\activate (CMD용, Git Bash로는 불가능)
    # python Study/API_GitHub_AWSDB.py --test (테스트 환경 실행 --test 옵션 필요)
    load_dotenv() # .env 파일에서 환경 변수 로드. 없을경우 넘어감

    # 테스트 모드일 경우 API 호출량과 배치 크기를 줄입니다.
    if is_test_mode:
        print("--- 🧪 테스트 모드로 실행합니다. (신규 2개 + 기존 2개) ---")
        display_count = 2
        batch_size = 2
        recent_articles_limit = 2
    else:
        display_count = 150
        batch_size = 15
        recent_articles_limit = 2000

    # 1. 네이버 뉴스 API 호출 /  매개변수 : 표시할 뉴스 개수
    raw_articles = naver_api_request(display_count=display_count)

    # 2. Gemini API 요청을 위한 임시 ID 부여 / 매개변수 : 뉴스 기사 리스트
    for i, item in enumerate(raw_articles):
        # 각 기사에 고유한 ID를 부여하여 프롬프트에 포함시킵니다.
        item['temp_id'] = f"article_{i}"

    processed_articles_for_db = []

    # 3. 뉴스 기사를 배치로 처리하며 Gemini API 호출 / 매개변수 : 뉴스 기사 리스트, 배치 크기
    for batch in chunked(raw_articles, batch_size):
        gemini_result = gemini_api_request(batch) 
        combine_result=combine_and_format_articles(batch, gemini_result) 
        processed_articles_for_db.extend(combine_result)

    # 4. 군집화
    print("--- 💾 DynamoDB에서 군집화 비교를 위한 최신 기사를 가져옵니다. ---")
    recent_db_articles = get_recent_articles(limit=recent_articles_limit)
    print(f"--- {len(recent_db_articles)}개의 기존 기사를 가져왔습니다. ---")
    
    CLUSTERING_THRESHOLD = 0.70 # 군집화 유사도 임계값 (0.0 ~ 1.0)

    clustered_articles=cluster_news(recent_db_articles, processed_articles_for_db, threshold=CLUSTERING_THRESHOLD)
    # 5. 데이터 저장0

    if clustered_articles:
        save_data(clustered_articles)
    else:
        print("--- 저장할 새로운 기사가 없습니다. ---")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="뉴스 데이터를 수집하고 분석하여 DynamoDB에 저장합니다.")
    parser.add_argument(
        '--test', 
        action='store_true', 
        help='스크립트를 테스트 모드로 실행합니다. (2개 기사만 처리)'
    )
    args = parser.parse_args()
    main(is_test_mode=args.test)
