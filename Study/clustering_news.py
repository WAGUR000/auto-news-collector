import torch
from sentence_transformers import SentenceTransformer, util
import uuid
from collections import defaultdict

# 모델: 한국어 성능이 뛰어난 SBERT 모델 사용
MODEL_NAME = 'jhgan/ko-sroberta-multitask'
device = 'cuda' if torch.cuda.is_available() else 'cpu'
sbert_model = SentenceTransformer(MODEL_NAME, device=device)

def cluster_news(recent_db_articles, processed_articles_for_db, threshold=0.75):
    # 1. 전체 기사 병합
    # recent_db_articles: 이미 clusterId가 부여된 과거 기사들
    # processed_articles_for_db: 새로 수집되어 clusterId가 없는 기사들
    all_articles = recent_db_articles + processed_articles_for_db
    
    # 2. 카테고리별 분리 (기존 로직 유지)
    articles_by_cat = defaultdict(list)
    for idx, article in enumerate(all_articles):
        cat = article.get('main_category', '기타')
        articles_by_cat[cat].append(idx)

    print(f"--- 군집화 시작 (Threshold: {threshold}) ---")
    
    # [중요] 새로 수집된 기사들만 골라내기 위한 인덱스 범위 계산
    new_article_start_idx = len(recent_db_articles) 

    for category, indices in articles_by_cat.items():
        if not indices: continue
        
        current_articles = [all_articles[i] for i in indices]
        
        # 임베딩 텍스트 구성 (기존 로직 유지)
        corpus = []
        for a in current_articles:
            if a.get('topic') and len(a['topic']) > 5:
                text = f"{a['topic']} {a['title']}"
            else:
                text = f"{a['title']} {a.get('description', '')[:50]}"
            corpus.append(text)
        
        # 임베딩 및 군집화
        embeddings = sbert_model.encode(corpus, convert_to_tensor=True, show_progress_bar=False)
        clusters = util.community_detection(embeddings, min_community_size=1, threshold=threshold)
        
        # --- [핵심 수정 부분: ID 상속 로직] ---
        for cluster in clusters:
            existing_cluster_id = None
            
            # 1. 이 군집 안에 '과거 기사(DB에서 온 기사)'가 있는지 확인
            for local_idx in cluster:
                global_idx = indices[local_idx]
                # 과거 기사이고, 이미 clusterId가 있다면 그 ID를 후보로 선정
                if global_idx < new_article_start_idx:
                    existing_id = all_articles[global_idx].get('clusterId')
                    if existing_id:
                        existing_cluster_id = existing_id
                        break # 하나라도 찾으면 그것을 사용 (같은 이슈로 간주)
            
            # 2. ID 결정 (과거 ID가 있으면 상속, 없으면 신규 발급)
            if existing_cluster_id:
                final_cluster_id = existing_cluster_id
                # print(f"Existing Cluster ID reused: {final_cluster_id}")
            else:
                final_cluster_id = uuid.uuid4().hex
            
            # 3. 대표 기사 선정 (기존 로직 유지)
            cluster_emb = embeddings[cluster]
            centroid = torch.mean(cluster_emb, dim=0)
            sims = util.cos_sim(centroid, cluster_emb)[0]
            best_local_idx = torch.argmax(sims).item()
            
            # 4. 결과 할당
            for i, local_idx in enumerate(cluster):
                global_idx = indices[local_idx]
                
                # 새로 수집된 기사(processed_articles_for_db)에 대해서만 값 업데이트
                # (과거 기사는 이미 DB에 있으므로 업데이트 불필요하거나, 필요시 업데이트)
                if global_idx >= new_article_start_idx:
                    all_articles[global_idx]['clusterId'] = final_cluster_id
                    
                    # 대표 기사 여부는 '현재 배치 내'에서 결정
                    all_articles[global_idx]['is_representative'] = 1 if i == best_local_idx else 0
                    
                    # [팁] 만약 과거 기사의 Topic이 더 좋다면 그걸 가져오는 로직을 추가할 수도 있음

    # 새로 수집된 기사만 반환 (이제 과거 기사와 같은 ID를 가질 수 있음)
    return all_articles[new_article_start_idx:]