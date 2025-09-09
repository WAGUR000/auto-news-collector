import boto3
import os
from datetime import datetime
import requests 
from urllib.parse import quote 
import pendulum 



# GitHub Actions 환경에서는 키를 직접 넣지 않아도 알아서 인증됩니다.
dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-2')
table = dynamodb.Table('News_Data_DB') # 실제 테이블 이름으로 변경

def save_data(articles_list):
    """DynamoDB의 BatchWriter를 사용해 여러 항목을 한번에 효율적으로 저장합니다."""
    try:
        # with 문을 사용하면 작업이 끝날 때 자동으로 데이터를 전송합니다.
        with table.batch_writer() as batch:
            for item in articles_list:
                # 개별 항목을 배치 작업에 추가합니다.
                batch.put_item(Item=item)
        print(f"{len(articles_list)}개의 데이터 저장 성공.")
    except Exception as e:
        print("에러 발생:", e)

if __name__ == "__main__":

    import requests
    from urllib.parse import quote

    NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID")
    NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET")
        
    keyword = "뉴스"
    enc_keyword = quote(keyword)
    url = f"https://openapi.naver.com/v1/search/news.json?query={enc_keyword}&display=100&start=1&sort=date"
    headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET}

    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    news_data = response.json()
        
    processed_articles = []
    for item in news_data.get("items", []):
         pub_date_obj = pendulum.from_format(item.get("pubDate"), 'ddd, DD MMM YYYY HH:mm:ss ZZ', tz='Asia/Seoul')
         processed_articles.append({
            "title": item.get("title", "").replace("<b>", "").replace("</b>", "").replace("&quot;", "\""),
            "originallink": item.get("originallink"),
            "News": item.get("link"),
            "description": item.get("description", "").replace("<b>", "").replace("</b>", "").replace("&quot;", "\""),
            "pub_date": pub_date_obj.to_iso8601_string()
        })
    save_data(processed_articles)
