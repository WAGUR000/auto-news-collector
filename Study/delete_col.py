import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-2')
table = dynamodb.Table('News_Data_DB')

# 삭제할 속성들
attributes_to_remove = "REMOVE #c1, #c2, #l, #t"
expression_attribute_names = {
    '#c1': 'category1',
    '#c2': 'category2',
    '#l': 'link',
    '#t': 'topics'
}

# Scan 페이지네이션
scan_kwargs = {}
removed_count = 0
last_evaluated_key = None

while True:
    if last_evaluated_key:
        scan_kwargs['ExclusiveStartKey'] = last_evaluated_key
    
    response = table.scan(**scan_kwargs)
    items = response.get('Items', [])
    last_evaluated_key = response.get('LastEvaluatedKey')
    
    for item in items:
        try:
            # 주 키 속성 이름을 테이블 스키마에 맞게 수정해야 함
            # 예시: 'News'가 파티션 키이고 'url'이 정렬 키일 경우
            key = {'News': item['News']}
            # 만약 정렬 키가 있다면 아래와 같이 추가
            # key = {'News': item['News'], 'url': item['url']}
            
            table.update_item(
                Key=key,
                UpdateExpression=attributes_to_remove,
                ExpressionAttributeNames=expression_attribute_names
            )
            removed_count += 1
            
        except ClientError as e:
            # ConditionalCheckFailedException 등 특정 오류 처리
            print(f"오류: {e.response['Error']['Message']} - 아이템: {item}")
        except Exception as e:
            print(f"일반 에러: {e} - 아이템: {item}")

    # 모든 항목을 처리했는지 확인
    if not last_evaluated_key:
        break

print(f"총 {removed_count}개의 항목에서 속성 삭제 완료.")