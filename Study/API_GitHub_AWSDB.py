import pendulum
from datetime import datetime
import argparse
from api_handler import naver_api_request, groq_api_request
from dotenv import load_dotenv
from aws_handler import get_recent_articles, save_data
from clustering_news import cluster_news
from data_processer import chunked, update_articles_with_topic
from predict import NewsClassifier
from extract_keywords import get_keywords
from kiwipiepy import Kiwi

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
        display_count = 100
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
        clean_title =article.get('title', '')
        clean_desc = article.get('description', '')
        
        # 모델 예측 수행 (predict.py)
        analysis_result = classifier.predict(clean_title, clean_desc)
        
        # 결과 업데이트 (기존 article 딕셔너리에 분석 필드 추가)
        article.update(analysis_result)
        
        # 정제된 텍스트로 덮어쓰기 (선택 사항, Groq 및 DB 저장을 위해 추천)
        article['title'] = clean_title
        article['description'] = clean_desc
        
        analyzed_articles.append(article)

    # 3. 군집화
    print("--- 💾 DynamoDB에서 군집화 비교를 위한 최신 기사를 가져옵니다. ---")
    recent_db_articles = get_recent_articles(limit=recent_articles_limit)
    print(f"--- {len(recent_db_articles)}개의 기존 기사를 가져왔습니다. ---")
    CLUSTERING_THRESHOLD = 0.70 # 군집화 유사도 임계값 (0.0 ~ 1.0)
    clustered_articles=cluster_news(recent_db_articles, analyzed_articles, threshold=CLUSTERING_THRESHOLD)

    # 4. Groq API 요청을 위한 임시 ID 부여 / 매개변수 : 뉴스 기사 리스트
    prompt_targets = []  # LLM에 실제로 보낼 기사들만 담을 리스트

    for i, item in enumerate(clustered_articles):
        # 신규 기사인지 확인 (raw_articles에 있던 것인지 판별하는 로직 필요, 여기선 is_new 플래그 가정)
        # 만약 cluster_news가 신규 기사 리스트만 반환한다면 is_new 체크 불필요
        # 대표 기사인지(is_representative == 1)만 확인
        if item.get('is_representative') == 1:
            item['temp_id'] = f"article_{i}"
            prompt_targets.append(item)
    
    print(f"--- 🤖 요약 및 토픽 생성이 필요한 기사: {len(prompt_targets)}개 ---")
    
    groq_processed_results = []

    # 5. 뉴스 기사를 배치로 처리하며 Groq API 호출 / 매개변수 : 뉴스 기사 리스트, 배치 크기
    for batch in chunked(prompt_targets, batch_size):
        groq_result = groq_api_request(batch) 
        updated_batch = update_articles_with_topic(batch, groq_result) 
        groq_processed_results.extend(updated_batch)
    # 5-1. topic 생성 기사와 기존 기사를 병합
    # 5-1. Topic 생성 기사와 기존 기사를 병합
    # Groq 처리된 기사들의 결과를 원본 리스트(clustered_articles)에 반영
    
    # 빠른 검색을 위해 temp_id를 키로 하는 딕셔너리 생성
    groq_map = {item['temp_id']: item for item in groq_processed_results if 'temp_id' in item}

    final_articles_to_save = []
    
    for item in clustered_articles:
        # 1. Groq 처리가 된 기사 (대표 기사)
        if 'temp_id' in item and item['temp_id'] in groq_map:
            updated_item = groq_map[item['temp_id']]
            del updated_item['temp_id']
            final_articles_to_save.append(updated_item)
        
        # 2. [추가] Groq 대상이 아니었던 나머지 신규 기사들
        # (이미 cluster_news 함수가 신규 기사만 반환하므로 별도 조건 없이 추가하면 됩니다)
        else:
            # 혹시 temp_id가 남아있을 경우 제거
            if 'temp_id' in item:
                del item['temp_id']
            final_articles_to_save.append(item)

    # 6. 키워드 추출

    print("--- 🔑 키워드 추출을 진행합니다. ---")
    for article in final_articles_to_save:
        # extract.py의 get_keywords 함수 호출
        # row['topic'] 혹은 row['title']을 기반으로 추출함
        article['keywords'] = get_keywords(article)

    # 7. DynamoDB 저장을 위한 PK/SK 생성 및 데이터 정제
    print("--- 📝 DynamoDB 저장을 위한 PK/SK 생성 및 데이터 정제를 진행합니다. ---")
    valid_articles_to_save = []

    for article in final_articles_to_save:
        try:
            # 1. 원본 pubDate 문자열 확인 (네이버 API 필드명: pubDate)
            pub_date_str = article.get('pubDate', '').strip()
        
            if not pub_date_str:
                # pubDate가 없으면 pub_date(snake_case)가 있는지 한 번 더 확인 (혹시 모르니)
                pub_date_str = str(article.get('pub_date', '')).strip()
            
            if not pub_date_str:
                raise ValueError("pubDate 데이터가 비어있습니다.")

            # 2. 날짜 파싱 (사용자님이 작성하신 정확한 포맷 사용)
            # 예: "Tue, 09 Dec 2025 11:23:58 +0900"
            try:
                # 네이버 원본 포맷 시도
                dt_object = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %z")
            except ValueError:
                # 혹시라도 형식이 다르거나 이미 ISO 포맷인 경우 Pendulum으로 자동 파싱 시도
                dt_object = pendulum.parse(pub_date_str)

            # 3. Pendulum 객체 변환
            p_date = pendulum.instance(dt_object)

            # 4. 필드 생성
            # pub_date: 시:분:초가 모두 포함된 ISO 8601 문자열 (예: 2025-12-09T11:23:58+09:00)
            article['pub_date'] = p_date.to_iso8601_string()
        
            # PK: 날짜만 (예: 2025-12-09)
            article['PK'] = p_date.to_date_string()
        
            # SK: 시간+링크 (유니크 키)
            article['SK'] = f"{p_date.to_iso8601_string()}#{article.get('link', '')}"

            # 5. 불필요한 원본 삭제
            if 'pubDate' in article:
                del article['pubDate']

            # 6. 유효 리스트 추가
            valid_articles_to_save.append(article)

        except Exception as e:
            print(f"⚠️ 데이터 전처리 중 에러 발생 (건너뜀): {e}")
            print(f"   - 문제의 데이터: {article.get('title', '제목없음')}")

    # 8. 데이터 저장 (유효한 기사만)
    if valid_articles_to_save:
        print(f"--- 💾 총 {len(valid_articles_to_save)}개의 유효한 기사를 저장합니다. ---")
        save_data(valid_articles_to_save)
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
