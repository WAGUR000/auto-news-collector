import boto3
from botocore.exceptions import ClientError

# DynamoDB 클라이언트 생성
dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-2')
table = dynamodb.Table('News_Data_DB') # 실제 테이블 이름으로 변경

def migrate_data():
    try:
        # 1. DynamoDB 테이블 스캔
        response = table.scan()
        items = response['Items']
        
        # Pagination 처리를 위한 루프
        while 'LastEvaluatedKey' in response:
            response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items.extend(response['Items'])

        print(f"총 {len(items)}개의 항목을 찾았습니다.")

        for item in items:
            # 주 키(partition key)와 정렬 키(sort key)를 사용하여 특정 항목 업데이트
            # DynamoDB 테이블의 키 속성 이름에 맞게 변경하세요.
            key = {
                'News': item['News'] 
                # 정렬 키가 있다면 여기에 추가: 'sort_key': item['sort_key']
            }
            
            # 2. 데이터 변환 및 업데이트
            update_expression = "SET main_category = :main, sub_category = :sub REMOVE category_1, category_2"
            expression_attribute_values = {
                ':main': item.get('category_1'),
                ':sub': item.get('category_2')
            }
            
            # category_1 또는 category_2가 없는 항목은 업데이트하지 않도록 조건 추가
            condition_expression = "attribute_exists(category_1) OR attribute_exists(category_2)"
            
            try:
                table.update_item(
                    Key=key,
                    UpdateExpression=update_expression,
                    ExpressionAttributeValues=expression_attribute_values,
                    ConditionExpression=condition_expression
                )
                print(f"항목 {key} 업데이트 완료.")
            except ClientError as e:
                # 속성이 없는 항목은 에러를 무시하거나 처리
                if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                    print(f"항목 {key}에는 변경할 속성이 없어 업데이트를 건너뜁니다.")
                else:
                    raise

    except ClientError as e:
        print(e.response['Error']['Message'])

if __name__ == '__main__':
    migrate_data()