# C:\GitHub\Study\extract.py

import json
from kiwipiepy import Kiwi

# Kiwi 초기화 (전역)
try:
    kiwi = Kiwi()
except:
    kiwi = None

stop_words = {
    # 기존 리스트
    '관련', '개최', '한국', '공개', '소통', '논란', '상황', '가능', '참석',
    '발언', '의혹', '사건', '예정', '진행', '결과', '보도', '사실', '경우',
    '때문', '정도', '이유', '자신', '문제', '내용', '부분', '시작', '포함',
    '주요', '대상', '기준', '확인', '이후', '이전', '가운데', '입장', '기자',
    '뉴스', '오전', '오후', '이번', '오늘', '내일', '어제',

    # 기사 메타·행사 표현
    '발표', '실시', '출범', '참가', '참여', '수상', '선정', '전달', '기탁',
    '마련', '운영', '제공', '진행', '시상식', '행사', '회의',

    # 지명·기관 일반어
    '시', '군', '구', '정부', '당국', '기관', '위원회', '공사', '그룹',
    '협회', '단체', '업계', '기업', '회사', '증권', '은행',

    # 증시·투자 일반어
    '장중', '상승', '하락', '약보합', '강세', '약세', '마감', '출발',
    '거래', '지수', '시장', '투자', '자산', '자금', '매수', '매도',

    # 추상 명사·관용구
    '분위기', '수준', '변화', '확대', '축소', '필요', '대책', '논의',
    '이슈', '현안', '역할', '효과', '전략', '상황', '가능성'
}

def get_keywords(article):
    """
    기사(딕셔너리)를 받아 핵심 키워드 리스트 ['단어1', '단어2']를 반환합니다.
    (절대로 [{"S":...}] 형태나 JSON 문자열을 반환하지 않습니다.)
    """
    if not kiwi: return []

    # topic 우선, 없으면 title 사용
    target_text = article.get('topic', '')
    if len(str(target_text)) < 2:
        target_text = article.get('title', '')
    
    if len(str(target_text)) < 2: 
        return []
    
    try:
        results = kiwi.analyze(target_text, top_n=1)
        if not results: return []
        
        tokens = results[0][0]
        keywords = []
        
        for token in tokens:
            if token.tag in ['NNG', 'NNP', 'SL']:
                if len(token.form) > 1 or token.tag == 'SL':
                    if token.form not in stop_words:
                        keywords.append(token.form)
        
        # 중복 제거
        unique_keywords = list(set(keywords))
        
        # [수정 전]
        # dynamo_format = [{"S": k} for k in unique_keywords]
        # return json.dumps(dynamo_format, ensure_ascii=False)
        
        # [수정 후] ★★★ 그냥 리스트 반환하세요! ★★★
        # boto3가 알아서 DynamoDB 형식으로 저장해줍니다.
        return unique_keywords 
        
    except Exception as e:
        # print(f"Keyword extraction error: {e}")
        return []