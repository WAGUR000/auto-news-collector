import json
from kiwipiepy import Kiwi
import re # 특수문자 제거를 위해 추가

# Kiwi 초기화
try:
    kiwi = Kiwi()
except:
    kiwi = None

# [이전 단계에서 보강한 stop_words 그대로 사용]
stop_words = {
    # ... (위에서 작성한 리스트 그대로 유지) ...
    '관련', '개최', '한국', '공개', '소통', '논란', '상황', '가능', '참석',
    '발언', '의혹', '사건', '예정', '진행', '결과', '보도', '사실', '경우',
    '때문', '정도', '이유', '자신', '문제', '내용', '부분', '시작', '포함',
    '주요', '대상', '기준', '확인', '이후', '이전', '가운데', '입장', '기자',
    '뉴스', '오전', '오후', '이번', '오늘', '내일', '어제', '남자', '서비스',
    '국민', '정보', '개편', '광고',
    '발표', '실시', '출범', '참가', '참여', '수상', '선정', '전달', '기탁',
    '마련', '운영', '제공', '진행', '시상식', '행사', '회의', '체결', '협력',
    '속보', '단독', '종합', '특징주', '포토', '영상', '1보', '2보', '기획', 
    '연재', '인사', '부고', '동정', '팩트', '체크',
    '시', '군', '구', '정부', '당국', '기관', '위원회', '공사', '그룹',
    '협회', '단체', '업계', '기업', '회사', '증권', '은행', '센터', '재단',
    '장중', '상승', '하락', '약보합', '강세', '약세', '마감', '출발',
    '거래', '지수', '시장', '투자', '자산', '자금', '매수', '매도', '급등', '급락',
    '원', '달러', '퍼센트', '포인트', '건', '명', '개', '대', '배', '만', '억', '조', '천',
    '분위기', '수준', '변화', '확대', '축소', '필요', '대책', '논의',
    '이슈', '현안', '역할', '효과', '전략', '상황', '가능성', '영향', '방안',
    '등', '및', '바', '수', '것', '점', '측', '쪽', '간', '곳', '만', '분', '위',
    '내', '외', '안', '전', '후',
    '주목', '강조', '평가', '전망', '분석', '관측', '예상', '우려', '기대',
    '지적', '주장', '시사', '배경', '목표', '달성', '추진', '강화', '지원',
    '성공', '실패', '극복', '도약', '대비', '돌파', '기록', '성료'
}

def get_keywords(article):
    """
    Topic과 Title을 결합하여 풍부한 맥락에서 핵심 키워드를 추출합니다.
    Description은 노이즈가 많아 제외합니다.
    """
    if not kiwi: return []

    # 1. Topic과 Title 가져오기 (None 방지)
    topic = article.get('topic', '')
    title = article.get('title', '')
    
    if topic is None: topic = ""
    if title is None: title = ""

    # 2. [핵심 변경] 두 텍스트 결합
    # Topic이 Title의 부분집합인 경우가 많지만, 
    # Title에만 있는 구체적 정보(숫자, 풀네임)를 놓치지 않기 위해 둘 다 씁니다.
    target_text = f"{topic} {title}"
    
    # 텍스트가 너무 짧으면 빈 리스트
    if len(target_text.strip()) < 2: 
        return []
    
    try:
        # 3. 형태소 분석
        results = kiwi.analyze(target_text, top_n=1)
        if not results: return []
        
        tokens = results[0][0]
        keywords = []
        
        for token in tokens:
            # NNG(일반명사), NNP(고유명사), SL(외국어) 태그만 추출
            if token.tag in ['NNG', 'NNP', 'SL']:
                # 한 글자 제외 (외국어는 허용)
                if len(token.form) > 1 or token.tag == 'SL':
                    if token.form not in stop_words:
                        keywords.append(token.form)
        
        # 4. 중복 제거 및 순서 보존
        # Topic과 Title을 합쳤으니 중복 단어가 많이 나오겠지만 여기서 다 걸러집니다.
        unique_keywords = list(dict.fromkeys(keywords))
        
        return unique_keywords 
        
    except Exception as e:
        return []