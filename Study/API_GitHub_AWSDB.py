import pendulum
from datetime import datetime
import argparse
from api_handler import naver_api_request, groq_api_request
from dotenv import load_dotenv
from aws_handler import get_recent_articles, save_data
from clustering_news import cluster_news
from data_processer import chunked, update_articles_with_topic, clean_text, data_cleaning, bulk_insert_articles
from predict import NewsClassifier
from extract_keywords import get_keywords
from kiwipiepy import Kiwi
import psycopg2
import os


# 전역 Kiwi 객체 (함수들이 참조함)
kiwi = Kiwi()

# 1. 소분류/감정 분석용 토크나이저
def korean_tokenizer(text):
    return [t.form for t in kiwi.tokenize(text) if t.tag in ['NNG', 'NNP', 'VA', 'XR', 'MAG', 'SL']]

# 2. 중요도 분석용 토크나이저
def importance_tokenizer(text):
    return [t.form for t in kiwi.tokenize(text) if t.tag in ['NNG', 'NNP', 'XR', 'SN']]

# 3. 대분류용 클래스 토크나이저 (클래스로 학습했다면 필요)
class KiwiTokenizer:
    def __init__(self):
        self.kiwi = Kiwi()
    def __call__(self, text):
        return [t.form for t in self.kiwi.tokenize(text) if t.tag in ['NNG', 'NNP']]
    def __getstate__(self):
        state = self.__dict__.copy()
        if 'kiwi' in state: del state['kiwi']
        return state
    def __setstate__(self, state):
        self.__dict__.update(state)
        self.kiwi = Kiwi()

def main(is_test_mode=False): #is_test_mode: 테스트 모드 여부. 기본값은 False이고 --test를 통해 매개변수 입력시 테스트 모드로 실행
    # 로컬 테스트
    # .\venv\Scripts\activate (CMD용, Git Bash로는 불가능)
    # python Study/API_GitHub_AWSDB.py --test (테스트 환경 실행 --test 옵션 필요)
    load_dotenv() # .env 파일에서 환경 변수 로드. 없을경우 넘어감

    # 테스트 모드일 경우 API 호출량과 배치 크기를 줄입니다.
    if is_test_mode:
        print("--- 🧪 테스트 모드로 실행합니다. (신규 2개 + 기존 2개) ---")
        display_count = 30
        batch_size = 10
        recent_articles_limit = 500
    else:
        display_count = 200
        batch_size = 20
        recent_articles_limit = 2000

    # 1. 네이버 뉴스 API 호출 /  매개변수 : 표시할 뉴스 개수
    raw_articles = naver_api_request(display_count=display_count)
    classifier = NewsClassifier()
    # 2. LM기반 중요도, 감정분석, 대/소분류
    analyzed_articles = [] # 분석이 완료된 기사를 담을 리스트

    for article in raw_articles:
        # HTML 태그 정제
        clean_title =clean_text(article.get('title', ''))
        clean_desc = clean_text(article.get('description', ''))

        # 정제된 텍스트로 덮어쓰기
        article['title'] = clean_title
        article['description'] = clean_desc

        analysis_result = classifier.predict(clean_title, clean_desc)
        
        # 결과 업데이트 (기존 article 딕셔너리에 분석 필드 추가)
        article.update(analysis_result)
        
        analyzed_articles.append(article)

    # 3. 군집화
    print("--- 💾 DynamoDB에서 군집화 비교를 위한 최신 기사를 가져옵니다. ---")
    recent_db_articles = get_recent_articles(limit=recent_articles_limit)
    print(f"--- {len(recent_db_articles)}개의 기존 기사를 가져왔습니다. ---")
    CLUSTERING_THRESHOLD = 0.77 # 군집화 유사도 임계값 (0.0 ~ 1.0)
    clustered_articles=cluster_news(recent_db_articles, analyzed_articles, threshold=CLUSTERING_THRESHOLD)

    # 4. Groq API 요청을 위한 임시 ID 부여 / 매개변수 : 뉴스 기사 리스트
    prompt_targets = [] 
    for i, item in enumerate(clustered_articles):
        # 이미 cluster_news에서 신규 기사만 필터링되어 넘어옴
        if item.get('is_representative') == 1:
            item['temp_id'] = f"article_{i}"
            prompt_targets.append(item)
    
    print(f"--- 🤖 요약 및 토픽 생성이 필요한 기사: {len(prompt_targets)}개 ---")
    
    final_articles_to_save = []

    # 5. Groq API 호출 및 데이터 후처리 통합 수행
    # 한 번에 전체 리스트를 처리하는 방식이 아니라면 배치로 나눠서 호출 후 결과 모으기
    
    all_groq_results = []
    if prompt_targets:
        for batch in chunked(prompt_targets, batch_size):
            groq_result = groq_api_request(batch) 
            all_groq_results.extend(groq_result)
            
    # ★ 여기서 한 방에 처리 (Topic 병합, 전파, Outlet, PK/SK, Keyword 정제)
    # clustered_articles 전체(대표 기사 + 일반 기사)를 넘겨야 전파가 가능함
    final_articles_to_save = update_articles_with_topic(clustered_articles, all_groq_results)
    result=data_cleaning(final_articles_to_save)
    try: 
        conn_postgres=psycopg2.connect(
        host=os.environ.get("DB_HOST"),
        database=os.environ.get("DB_NAME"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD")
        )
    except Exception as e:
        print(f"⚠️ PostgreSQL 연결 실패: {e}")
        return None

    bulk_insert_articles(conn_postgres, result)

    # 6. 데이터 저장
    # if final_articles_to_save:
    #     print(f"--- 💾 총 {len(final_articles_to_save)}개의 유효한 기사를 저장합니다. ---")
    #     save_data(final_articles_to_save)
    # else:
    #     print("--- 저장할 새로운 기사가 없습니다. ---")
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="뉴스 데이터를 수집하고 분석하여 DynamoDB에 저장합니다.")
    parser.add_argument(
        '--test', 
        action='store_true', 
        help='스크립트를 테스트 모드로 실행합니다. (2개 기사만 처리)'
    )

    args = parser.parse_args()
    main(is_test_mode=args.test)
