import pendulum
from datetime import datetime  # [수정] 모듈 대신 클래스를 import 해야 strptime 사용 가능
from urllib.parse import urlparse
from news_organization_lists import NEWS_OUTLET_MAP
from extract_keywords import get_keywords  

def chunked(iterable, n): 
    """iterable을 n개씩 묶어서 반환 (Gemini/Groq API 배치 처리용)"""
    for i in range(0, len(iterable), n):
        yield iterable[i:i + n]

def clean_text(text): 
    """텍스트 정리 함수 (HTML 태그 제거 및 특수문자 변환)"""
    if not isinstance(text, str):
        return ""
    return text.replace("<b>", "").replace("</b>", "").replace("&quot;", "\"")

def get_outlet_name(original_link): 
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
    # 1. 빠른 검색을 위한 Topic 맵 생성
    topic_map = {item['temp_id']: item['topic'] for item in groq_results if 'topic' in item and 'temp_id' in item}
    
    # 군집 ID별 Topic 맵 생성 (전파용)
    cluster_topic_map = {}

    # [1차 순회] Topic 병합
    for article in original_articles:
        t_id = article.get('temp_id')
        if t_id and t_id in topic_map:
            article['topic'] = topic_map[t_id]
        
        if article.get('topic') and article.get('clusterId') is not None:
             cluster_topic_map[article['clusterId']] = article['topic']

    valid_articles = []
    
    print("--- 📝 기사 병합 및 DB 저장용 데이터 정제(PK/SK/Outlet/Keyword)를 시작합니다. ---")

    # [2차 순회] 정제 및 검증
    for article in original_articles:
        try:
            # 2. Topic 전파
            if not article.get('topic') and article.get('clusterId') in cluster_topic_map:
                article['topic'] = cluster_topic_map[article['clusterId']]

            if not article.get('topic'):
                article['topic'] = article.get('title', '')
                print(f"⚠️ Topic 생성 실패로 제목 사용: {article['title']}")

            # 3. Outlet 매핑
            target_link = article.get('originallink') or article.get('link', '')
            article['outlet'] = get_outlet_name(target_link)

            # 4. 키워드 추출
            try:
                # get_keywords는 이제 ['단어', '단어']를 반환합니다.
                raw_keywords = get_keywords(article)
            except Exception:
                raw_keywords = []

            # [안전장치] 만약 여전히 꼬여있다면 강제로 펴줍니다.
            final_keywords = []
            if isinstance(raw_keywords, list):
                for k in raw_keywords:
                    if isinstance(k, str):
                        final_keywords.append(k)
                    elif isinstance(k, dict) and 'S' in k: # {"S": "값"} 형태라면 값만 꺼냄
                         final_keywords.append(k['S'])
            
            # 여기서 article['keywords']는 무조건 ['A', 'B', 'C'] 형태여야 합니다.
            article['keywords'] = final_keywords

            # 5. 날짜 파싱
            pub_date_str = article.get('pubDate', '').strip()
            # 네이버 API 원본 필드가 없으면 가공된 필드 확인
            if not pub_date_str:
                pub_date_str = str(article.get('pub_date', '')).strip()
            
            if not pub_date_str:
                print(f"⚠️ 날짜 필드 없음 (Skip): {article.get('title')}")
                continue 

            try:
                # RFC 822 (Mon, 09 Dec...)
                dt_object = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %z")
            except ValueError:
                try:
                    # ISO 8601 등 기타 포맷 시도
                    dt_object = pendulum.parse(pub_date_str)
                except Exception:
                    print(f"⚠️ 날짜 파싱 실패 (Skip): {pub_date_str}")
                    continue
            
            p_date = pendulum.instance(dt_object)

            # 6. PK/SK 생성
            article['pub_date'] = p_date.to_iso8601_string()
            article['PK'] = p_date.to_date_string()
            article['SK'] = f"{p_date.to_iso8601_string()}#{article.get('link', '')}"

            # 불필요 필드 정리
            if 'pubDate' in article: del article['pubDate']
            if 'temp_id' in article: del article['temp_id']

            valid_articles.append(article)

        except Exception as e:
            print(f"❌ 데이터 정제 중 치명적 오류: {e} / 기사: {article.get('title')}")
            continue

    print(f"--- ✅ 처리 완료: {len(valid_articles)}건 정제됨 ---")
    return valid_articles