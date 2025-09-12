import boto3
import os
import requests
import pendulum
import google.generativeai as genai
from urllib.parse import quote
import json

# GitHub Actions 환경에서는 키를 직접 넣지 않아도 알아서 인증됩니다.
dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-2')
table = dynamodb.Table('News_Data_v1') # 실제 테이블 이름으로 변경

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

if __name__ == "__main__":
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID")
    NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET")

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash') #

    # 1. 네이버 뉴스 API 호출
    keyword = "뉴스"
    enc_keyword = quote(keyword)
    url = f"https://openapi.naver.com/v1/search/news.json?query={enc_keyword}&display=100&start=1&sort=date"
    headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        news_data = response.json()
        raw_articles = news_data.get("items", [])
    except requests.exceptions.RequestException as e:
        print(f"네이버 뉴스 API 호출 중 에러 발생: {e}")
        exit()

    # 2. 임시 라벨 추가 및 데이터 준비
    labeled_articles = []
    for i, item in enumerate(raw_articles):
        # 각 기사에 고유한 ID를 부여하여 프롬프트에 포함시킵니다.
        item['temp_id'] = f"article_{i}"
        labeled_articles.append(item)

    processed_articles_for_db = []

    # 3. 뉴스 기사를 배치로 처리하며 Gemini API 호출
    batch_size = 10 # 한 번에 처리할 기사 수. 토큰 수에 따라 조정 가능
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
                "sentiment": "긍정/부정/중립",
                "category1": "대분류",
                "category2": "소분류",
                "importance": "1~10 중요도"
              }},
              ...
            ]
            """
        )
        
        try:
            response = model.generate_content(prompt)
            json_str = response.text.strip('`').strip('json').strip()
            # 응답에서 JSON 파싱
            gemini_result = json.loads(json_str)

            # 4. Gemini API 응답과 원본 데이터 결합
            gemini_map = {item['temp_id']: item for item in gemini_result}
            
            for item in batch:
                temp_id = item['temp_id']
                if temp_id in gemini_map:
                    gemini_info = gemini_map[temp_id]
                    
                    pub_date_obj = pendulum.from_format(item.get("pubDate"), 'ddd, DD MMM YYYY HH:mm:ss ZZ', tz='Asia/Seoul')
                    
        
                    pub_date_str1 = pub_date_obj.format('YYYY-MM-DD')
                    link = item.get("link")

                    partition_key = pub_date_str1
                    sort_key = f"{pub_date_obj.to_iso8601_string()}#{link}"




                    # 최종 DynamoDB 저장용 데이터 생성
                    processed_articles_for_db.append({
                        "PK": partition_key, # 파티션 키. 날짜(YYYY-MM-DD)
                        "SK": sort_key, # 정렬 키. ISO 8601 형식의 날짜 + 링크 (유일성 보장)
                        "title": item.get("title", "").replace("<b>", "").replace("</b>", "").replace("&quot;", "\""),
                        "topic": gemini_info.get("topic"),
                        "importance": gemini_info.get("importance"),
                        "sentiment": gemini_info.get("sentiment"),
                        "main_category": gemini_info.get("category1"),
                        "sub_category": gemini_info.get("category2"),
                        "description": item.get("description", "").replace("<b>", "").replace("</b>", "").replace("&quot;", "\""),
                        "pub_date": pub_date_obj.to_iso8601_string(),
                        "originallink": item.get("originallink") # 네이버 뉴스링크가 아닌, 뉴스 제공처의 원본 링크
                    })

        except Exception as e:
            print(f"Gemini API 호출 또는 응답 처리 중 에러 발생: {e}")
            continue # 다음 배치로 이동

    # 5. 최종 데이터 저장
    if processed_articles_for_db:
        save_data(processed_articles_for_db)
    else:
        print("처리할 기사가 없습니다.")