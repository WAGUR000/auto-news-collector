import torch
from sentence_transformers import SentenceTransformer, util
import uuid
from collections import defaultdict

# 모델 로드 (전역 혹은 클래스 내부)
MODEL_NAME = 'jhgan/ko-sroberta-multitask'
device = 'cuda' if torch.cuda.is_available() else 'cpu'
sbert_model = SentenceTransformer(MODEL_NAME, device=device)

def cluster_news(recent_db_articles, processed_articles_for_db, threshold=0.75):
    """
    기존 기사와 새 기사를 합쳐 군집화를 수행합니다.
    - 기존 군집에 속하면: Topic과 ClusterID를 상속받습니다. (LLM 비용 절감)
    - 새로운 군집이면: 대표 기사를 선정하고 Topic 생성 요청 플래그를 켭니다.
    """
    # 1. 전체 기사 병합
    all_articles = recent_db_articles + processed_articles_for_db
    new_article_start_idx = len(recent_db_articles)
    
    # 2. 카테고리별 분리
    articles_by_cat = defaultdict(list)
    for idx, article in enumerate(all_articles):
        cat = article.get('main_category', '기타')
        articles_by_cat[cat].append(idx)

    print(f"--- 군집화 및 토픽 배정 시작 (Threshold: {threshold}) ---")
    
    for category, indices in articles_by_cat.items():
        if not indices: continue
        
        current_articles = [all_articles[i] for i in indices]
        
        # 임베딩 텍스트 구성: Topic이 없으면 Title + Description 사용
        corpus = []
        for a in current_articles:
            # 기존 DB 기사는 Topic이 있을 수 있으므로 활용
            if a.get('topic') and len(a['topic']) > 2:
                text = f"{a['topic']} {a['title']}"
            else:
                text = f"{a['title']} {a.get('description', '')[:100]}"
            corpus.append(text)
        
        # 임베딩 및 군집화
        embeddings = sbert_model.encode(corpus, convert_to_tensor=True, show_progress_bar=False)
        clusters = util.community_detection(embeddings, min_community_size=1, threshold=threshold)
        
        for cluster in clusters:
            existing_info = None # (clusterId, topic)
            
            # A. 이 군집 안에 '과거 기사(DB)'가 있는지 확인
            for local_idx in cluster:
                global_idx = indices[local_idx]
                if global_idx < new_article_start_idx:
                    target_article = all_articles[global_idx]
                    e_id = target_article.get('clusterId')
                    if e_id:
                        # 기존 ID와 Topic을 찾음 (하나라도 찾으면 그것을 기준점으로 사용)
                        e_topic = target_article.get('topic', '')
                        existing_info = (e_id, e_topic)
                        break 
            
            # B. 대표 기사 선정 (임베딩 중심점 계산)
            cluster_emb = embeddings[cluster]
            centroid = torch.mean(cluster_emb, dim=0)
            sims = util.cos_sim(centroid, cluster_emb)[0]
            best_local_idx = torch.argmax(sims).item()
            
            # C. 결과 할당 (새로 수집된 기사에 대해서만 값 업데이트)
            # 신규 군집일 경우를 대비해 새 ID 생성
            new_cluster_id = uuid.uuid4().hex
            
            for i, local_idx in enumerate(cluster):
                global_idx = indices[local_idx]
                
                # '새로 수집된 기사'만 처리
                if global_idx >= new_article_start_idx:
                    article = all_articles[global_idx]
                    
                    if existing_info:
                        # [Case 1: 상속] 기존 군집에 포함됨
                        article['clusterId'] = existing_info[0]
                        article['topic'] = existing_info[1] # 토픽 상속!
                        article['is_representative'] = 0    # 이미 기존 기사가 대표이므로 0

                    
                    else:
                        # [Case 2: 신규] 완전히 새로운 군집 탄생
                        article['clusterId'] = new_cluster_id
                        
                        # 대표 기사인지 확인
                        if i == best_local_idx:
                            article['is_representative'] = 1

                        else:
                            article['is_representative'] = 0

    # 새로 수집된 기사 리스트만 반환
    return all_articles[new_article_start_idx:]