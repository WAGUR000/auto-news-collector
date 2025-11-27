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
    


def combine_and_format_articles(original_articles, gemini_results):
    gemini_map = {item['temp_id']: item for item in gemini_results}
    processed_articles = []

    for item in original_articles: # 원본기사 하나씩 처리
        temp_id = item.get('temp_id')
        if temp_id in gemini_map:
            gemini_info = gemini_map[temp_id]
            
            # 중요도를 안전하게 정수형으로 변환합니다.
            importance_val = gemini_info.get("importance")
            try:
                # 문자열로 된 숫자('7')도 처리하기 위해 int()로 변환합니다.
                importance = int(importance_val)
            except (ValueError, TypeError):
                # 변환 실패 시(예: '높음', None) 기본값 5를 사용하고 로그를 남깁니다.
                print(f"Warning: 'importance' 값 '{importance_val}'을(를) 정수로 변환할 수 없어 기본값 5를 사용합니다. (temp_id: {temp_id})")
                importance = 5
            keywords = gemini_info.get("keywords", [])
            # 감정을 안전하게 실수형(float)으로 변환합니다.
            sentiment_val = gemini_info.get("sentiment")
            try:
                # 문자열로 된 숫자('7.5')나 정수(5)도 처리하기 위해 float()로 변환합니다.
                sentiment = float(sentiment_val)
            except (ValueError, TypeError):
                # 변환 실패 시(예: '중립', None) 기본값 5.0을 사용하고 로그를 남깁니다.
                print(f"Warning: 'sentiment' 값 '{sentiment_val}'을(를) 실수로 변환할 수 없어 기본값 5.0을 사용합니다. (temp_id: {temp_id})")
                sentiment = 5.0
            # 날짜 및 키 생성
            pub_date_obj = pendulum.from_format(item["pubDate"], 'ddd, DD MMM YYYY HH:mm:ss ZZ', tz='Asia/Seoul')
            original_link = item.get("originallink", "")
            link = item.get("link", "")
                
            formatted_article = {
                    "PK": pub_date_obj.to_date_string(),
                    "SK": f"{pub_date_obj.to_iso8601_string()}#{link}",
                    "title": clean_text(item.get("title", "")),
                    "topic": gemini_info.get("topic"),
                    "importance": importance,
                    "sentiment": sentiment,
                    "main_category": gemini_info.get("category1"),
                    "sub_category": gemini_info.get("category2"),
                    "description": clean_text(item.get("description", "")),
                    "pub_date": pub_date_obj.to_iso8601_string(),
                    "originallink": original_link,
                    "outlet": get_outlet_name(original_link),
                    "keywords": keywords
                }
            processed_articles.append(formatted_article)

    return processed_articles