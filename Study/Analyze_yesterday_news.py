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
table_name = 'News_Data_DBE'
table = dynamodb.Table(table_name)

# 예시: 특정 날짜의 뉴스 데이터 조회
def get_news_by_date(date):
    response = table.query(
        KeyConditionExpression=Key('date').eq(date)
    )
    return response.get('Items', [])

# 사용 예시
if __name__ == "__main__":
    yesterday = '2025-09-09'  # 예시 날짜
    news_items = get_news_by_date(yesterday)
    for item in news_items:
        print(item)