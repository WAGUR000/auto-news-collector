import json
from kiwipiepy import Kiwi

# 1. Kiwi 초기화 (사용자 사전 학습 과정 제거)
kiwi = Kiwi()

# 2. 불용어(Stopwords) 설정
stop_words = {
    '관련', '개최', '한국', '공개', '소통', '논란', '상황', '가능', '참석', 
    '발언', '의혹', '사건', '예정', '진행', '결과', '보도', '사실', '경우', 
    '때문', '정도', '이유', '자신', '문제', '내용', '부분', '시작', '포함',
    '주요', '대상', '기준', '확인', '이후', '이전', '가운데', '입장', '기자', '뉴스'
}

def get_keywords(row):
    # 이미 값이 있으면 유지 (재처리 방지)
    if 'keywords' in row and row['keywords'] and row['keywords'] != "[]":
        return row['keywords']
    
    # topic이 있으면 topic 우선, 없으면 title 사용 (데이터가 짧을 경우 대비)
    topic_text = row.get('topic', '') 
    target_text = topic_text if len(str(topic_text)) > 2 else row['title']
    
    if len(str(target_text)) < 2: 
        return "[]"
    
    try:
        # top_n=1: 가장 확률 높은 분석 결과 하나만 사용 (속도 최적화)
        results = kiwi.analyze(target_text, top_n=1)
        if not results: 
            return "[]"
        
        tokens = results[0][0]
        keywords = []
        
        for token in tokens:
            # 명사(NNG, NNP), 외국어(SL) 추출
            if token.tag in ['NNG', 'NNP', 'SL']:
                # 한 글자 제외 (단, 외국어는 허용)
                if len(token.form) > 1 or token.tag == 'SL':
                    if token.form not in stop_words:
                        keywords.append(token.form)
        
        # 중복 제거
        unique_keywords = list(set(keywords))
        
        # DynamoDB JSON 포맷 변환 [{"S": "값"}, ...]
        dynamo_format = [{"S": k} for k in unique_keywords]
        
        # 빈 리스트일 경우 "[]" 문자열 반환 (DynamoDB 저장 시 오류 방지)
        if not dynamo_format:
            return "[]"
            
        return json.dumps(dynamo_format, ensure_ascii=False)
        
    except Exception as e:
        print(f"Error parsing keywords: {e}")
        return "[]"
