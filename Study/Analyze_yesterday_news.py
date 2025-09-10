from boto3.dynamodb.conditions import Key
import boto3
import os
from datetime import datetime
import requests 
from urllib.parse import quote 
import pendulum 


# AWS 자격 증명 및 리전 설정
aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
region_name = 'ap-northeast-2'  # 예시: 서울 리전

# DynamoDB 리소스 생성
dynamodb = boto3.resource(
    'dynamodb',
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=region_name
)

# 테이블 이름 지정
table_name = 'News_Data_DB'
table = dynamodb.Table(table_name)


def get_yesterday_news():
    # 어제 날짜 구하기 (YYYY-MM-DD)
    yesterday = pendulum.now('Asia/Seoul').subtract(days=1).to_date_string()
    # pub_date가 어제 날짜로 시작하는 뉴스만 필터링
    response = table.scan()
    items = response.get('Items', [])
    yesterday_news = [
        item for item in items
        if item.get('pub_date', '').startswith(yesterday)
    ]
    return yesterday_news

if __name__ == "__main__":
    news_items = get_yesterday_news()
    for item in news_items:
        print(item)