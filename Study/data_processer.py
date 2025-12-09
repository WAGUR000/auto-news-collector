import  pendulum
from urllib.parse import urlparse
from news_organization_lists import NEWS_OUTLET_MAP

def chunked(iterable, n): # Gemini API 호출 시 배치 처리를 위한 함수
    #iterable을 n개씩 묶어서 반환
    for i in range(0, len(iterable), n):
        yield iterable[i:i + n]

def clean_text(text): # 텍스트 정리 함수 (제목, 설명같은 텍스트 필드에 사용)
    if not isinstance(text, str):
        return ""
    return text.replace("<b>", "").replace("</b>", "").replace("&quot;", "\"")

def get_outlet_name(original_link): # 언론사 도메인 매핑 함수
    """
    원본 링크에서 도메인을 추출하여 언론사 이름을 반환합니다.
    매핑되지 않은 경우 '기타언론사'를 반환합니다.
    """
    if not original_link:
        return '기타언론사'
    try:
        domain = urlparse(original_link).netloc
        return NEWS_OUTLET_MAP.get(domain, '기타언론사')
    except Exception:
        return '기타언론사'
    

def update_articles_with_topic(original_articles, groq_results):
    # groq_results: [{'temp_id': '...', 'topic': '...'}, ...]
    
    # 빠른 검색을 위한 맵 생성
    topic_map = {item['temp_id']: item['topic'] for item in groq_results if 'topic' in item}
    
    updated_count = 0
    for item in original_articles:
        temp_id = item.get('temp_id')
        if temp_id in topic_map:
            item['topic'] = topic_map[temp_id] # Topic 업데이트
            updated_count += 1
            
    print(f"--- {updated_count}개 기사의 Topic이 업데이트 되었습니다. ---")
    return original_articles