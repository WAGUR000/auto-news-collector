from boto3.dynamodb.conditions import Key
import boto3
import pendulum 

# --- 설정값 ---
AWS_REGION = 'ap-northeast-2'
DYNAMODB_TABLE_NAME = 'News_Data_v1'

# boto3가 환경에 따라 (GitHub Actions, 로컬 환경변수 등) 자동으로 자격 증명을 찾습니다.
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)

# 테이블 객체 생성
table = dynamodb.Table(DYNAMODB_TABLE_NAME)


def get_yesterday_news():
    # 어제 날짜 구하기 (YYYY-MM-DD)
    yesterday_str = pendulum.now('Asia/Seoul').subtract(days=1).to_date_string()
    
    # scan 대신 query를 사용하여 특정 파티션 키(어제 날짜)의 데이터만 효율적으로 조회합니다.
    response = table.query(
        KeyConditionExpression=Key('PK').eq(yesterday_str)
    )
    items = response.get('Items', [])
    # TODO: Paginator를 사용하여 1MB 이상의 결과도 모두 가져오도록 개선할 수 있습니다.
    return items
