import boto3
from boto3.dynamodb.conditions import Key
import pendulum
from decimal import Decimal
import json


DYNAMODB_TABLE_NAME = 'News_Data_v1' 
AWS_REGION = 'ap-northeast-2'
# GitHub Actions 환경에서는 키를 직접 넣지 않아도 알아서 인증됩니다.
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
table = dynamodb.Table(DYNAMODB_TABLE_NAME)




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

