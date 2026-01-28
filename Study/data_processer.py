import pendulum
from datetime import datetime  # [수정] 모듈 대신 클래스를 import 해야 strptime 사용 가능
from urllib.parse import urlparse
from news_organization_lists import NEWS_OUTLET_MAP
from extract_keywords import get_keywords  
import html  # 파이썬 내장 모듈
import pandas as pd
import os
import json
import numpy as np
import csv
from decimal import Decimal
from psycopg2.extras import execute_values

def chunked(iterable, n): 
    """iterable을 n개씩 묶어서 반환 (Gemini/Groq API 배치 처리용)"""
    for i in range(0, len(iterable), n):
        yield iterable[i:i + n]
def clean_text(text): 
    """텍스트 정리 함수 (HTML 태그 제거 및 모든 특수문자 자동 변환)"""
    if not isinstance(text, str):
        return ""
    
    # 1. 태그 제거 (기존 방식 유지해도 무방, re 모듈 추천)
    text = text.replace("<b>", "").replace("</b>", "")
    
    # 2. 모든 HTML 엔티티(&quot;, &amp;, &lt; 등) 한 방에 변환
    text = html.unescape(text) 
    
    return text.strip()

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
    requested_ids = {a['temp_id'] for a in original_articles if 'temp_id' in a}
    received_ids = {r['temp_id'] for r in groq_results if 'temp_id' in r}
    
    missing_ids = requested_ids - received_ids
    if missing_ids:
        print(f"🚨 [치명적 오류] 요청했지만 응답받지 못한 temp_id: {missing_ids}")
        # 여기서 missing_ids에 해당하는 기사들은 토픽 생성에 실패한 것입니다.
    
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
                print(f"⚠️ Topic 생성 실패로 제목 사용: {article['title'], article['clusterId'],article['is_representative']}")

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

def process_keywords(val):
            # 1. 값이 아예 없거나 None인 경우 (단일 값 체크에 안전한 방식)
            if val is None or (isinstance(val, float) and np.isnan(val)):
                return json.dumps([], ensure_ascii=False)
            
            # 2. 이미 리스트 또는 튜플인 경우 (DynamoDB에서 가장 흔한 형태)
            if isinstance(val, (list, tuple, np.ndarray)):
                # 리스트 내부에 Decimal 객체가 있을 수 있으므로 일반 객체로 변환 시도
                clean_list = [float(i) if isinstance(i, Decimal) else i for i in val]
                return json.dumps(list(clean_list), ensure_ascii=False)
            
            # 3. 문자열 형태인 경우 (CSV/V4 소스 등)
            if isinstance(val, str):
                val = val.strip()
                if not val or val == "[]":
                    return json.dumps([], ensure_ascii=False)
                try:
                    # 기존 로직: 대괄호 제거 및 따옴표 정리
                    s = val.strip("[]")
                    res = [tok.strip().strip("'").strip('"') for tok in s.split(",") if tok.strip()]
                    return json.dumps(res, ensure_ascii=False)
                except:
                    return json.dumps([], ensure_ascii=False)
            
            return json.dumps([], ensure_ascii=False)


def data_cleaning(articles):
    if not articles:
        print("수집할 새로운 데이터가 없습니다.")
    else:
        df = pd.DataFrame(articles)
        # 4. 데이터 전처리 (순서 중요)
        # DynamoDB의 Decimal 타입을 float/int로 변환 (CSV 저장 시 에러 방지)
        for col in df.columns:
            if df[col].apply(lambda x: isinstance(x, Decimal)).any():
                df[col] = df[col].apply(lambda x: float(x) if isinstance(x, Decimal) else x)

        # 불필요 컬럼 제거 및 link 추출
        df = df.drop(columns=['penalty_applied'], errors='ignore')
        if 'SK' in df.columns:
            df['link'] = df['SK'].str.split('#').str[1]
            # SK는 나중에 pk로 변환될 PK가 있으므로 삭제
            df = df.drop(columns=['SK'])

        # 5. 핵심 로직 적용
        # 
        
        # 키워드 처리 함수

        if 'keywords' in df.columns:
            df['keywords'] = df['keywords'].apply(process_keywords)
        
        # 설명 및 기타 결측치 처리
        df['description'] = df['description'].fillna('')
        df['is_representative'] = df['is_representative'].fillna(True).astype(bool)
        # 6. 컬럼 표준화 (DB 적재용)
        MASTER_COLUMNS = [
            'pk', 'originallink', 'main_category', 'outlet', 'pub_date',
            'description', 'title', 'is_representative', 'importance', 'clusterid',
            'sub_category', 'topic', 'sentiment', 'keywords', 'link'
        ]

        def finalize_for_db(target_df):
            # 소문자 변환 (PK -> pk, clusterId -> clusterid 등)
            target_df.columns = [col.lower() for col in target_df.columns]
            
            # 누락된 컬럼 기본값 채우기
            for col in MASTER_COLUMNS:
                if col not in target_df.columns:
                    target_df[col] = ""
            
            # 중요도(importance) 등 숫자형 기본값 보정 (필요시)
            target_df['importance'] = pd.to_numeric(target_df['importance'], errors='coerce').fillna(0).astype(int)
            
            return target_df[MASTER_COLUMNS]

        df = finalize_for_db(df)

        # 7. 필수 식별자 없는 행 최종 제거
        df.dropna(subset=['pk', 'link'], inplace=True)
        print(df.info())
        # 8. 저장
        return df



def bulk_insert_articles(conn, articles_df):
    """
    articles_df: Pandas DataFrame (data_cleaning의 결과물)
    """
    print("--- 📝 PostgreSQL 벌크 삽입 시작 ---")
    
    # 1. 만약 리스트로 들어왔다면 다시 DF로 변환하거나, 
    # 여기서는 메인에서 리스트로 변환해서 넘긴다고 가정하고 처리합니다.
    if isinstance(articles_df, pd.DataFrame):
        data_list = articles_df.to_dict('records')
    else:
        data_list = articles_df

    cur = conn.cursor()
    
    # 2. 튜플 리스트로 변환 (순서 주의: SQL문의 컬럼 순서와 일치해야 함)
    # data_cleaning에서 이미 lowercase 처리가 되었으므로 키 값은 소문자입니다.
    data_tuples = [
        (
            a.get('pk'), 
            a.get('link'),
            a.get('originallink'),
            a.get('main_category'),
            a.get('outlet'),
            a.get('pub_date'),
            a.get('description'),
            a.get('title'),
            a.get('is_representative', False),
            int(a.get('importance', 0)), # smallint 대응
            a.get('clusterid'),
            a.get('sub_category'),
            a.get('topic'),
            float(a.get('sentiment', 0.0)),
            a.get('keywords') # data_cleaning에서 이미 json.dumps 문자열로 변환됨
        ) for a in data_list
    ]

    query = """
        INSERT INTO articles_table (
            pk, link, originallink, main_category, outlet, 
            pub_date, description, title, is_representative, 
            importance, clusterid, sub_category, topic, 
            sentiment, keywords
        ) VALUES %s
        ON CONFLICT (pk, link) DO UPDATE SET
            topic = EXCLUDED.topic,
            sentiment = EXCLUDED.sentiment,
            importance = EXCLUDED.importance,
            keywords = EXCLUDED.keywords;
    """

    try:
        execute_values(cur, query, data_tuples)
        conn.commit()
        print(f"✅ 총 {len(data_tuples)}건 처리 완료 (중복 업데이트 포함)")
    except Exception as e:
        conn.rollback()
        print(f"❌ 벌크 삽입 중 에러 발생: {e}")
        raise e # 에러를 다시 던져서 로그에 찍히게 함
    finally:
        cur.close()
        