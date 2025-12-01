import torch
from sentence_transformers import SentenceTransformer, util
import uuid
from collections import defaultdict

# 모델: 한국어 성능이 뛰어난 SBERT 모델 사용
MODEL_NAME = 'jhgan/ko-sroberta-multitask'
device = 'cuda' if torch.cuda.is_available() else 'cpu'
sbert_model = SentenceTransformer(MODEL_NAME, device=device)

def cluster_news(recent_db_articles, processed_articles_for_db, threshold=0.82):
    # 1. 전체 기사 병합 및 초기화
    all_articles = recent_db_articles + processed_articles_for_db
    for article in all_articles:
        article['clusterId'] = uuid.uuid4().hex
        article['is_representative'] = 1 

    # 2. 카테고리별 분리 (정치 vs 연예 섞임 방지)
    articles_by_cat = defaultdict(list)
    for idx, article in enumerate(all_articles):
        cat = article.get('main_category', '기타')
        articles_by_cat[cat].append(idx)

    print(f"--- 군집화 시작 (Model: {MODEL_NAME}, Threshold: {threshold}) ---")
    
    total_clusters = 0

    for category, indices in articles_by_cat.items():
        if not indices: continue
        
        current_articles = [all_articles[i] for i in indices]
        
        # [핵심 변경] 임베딩 텍스트 구성: Topic을 최우선으로 사용
        corpus = []
        for a in current_articles:
            # Topic이 있으면 Topic + Title, 없으면 Title + Description
            if a.get('topic') and len(a['topic']) > 5:
                text = f"{a['topic']} {a['title']}"
            else:
                text = f"{a['title']} {a.get('description', '')[:50]}"
            corpus.append(text)
        
        # 임베딩 생성
        embeddings = sbert_model.encode(corpus, convert_to_tensor=True, show_progress_bar=False)
        
        # 군집화 수행
        # min_communit
        clusters = util.community_detection(embeddings, min_community_size=1, threshold=threshold)
        total_clusters += len(clusters)
        
        # 결과 반영
        for cluster in clusters:
            cluster_id = uuid.uuid4().hex
            
            # 중심 기사(Representative) 선정
            cluster_emb = embeddings[cluster]
            centroid = torch.mean(cluster_emb, dim=0)
            sims = util.cos_sim(centroid, cluster_emb)[0]
            best_local_idx = torch.argmax(sims).item()
            
            for i, local_idx in enumerate(cluster):
                global_idx = indices[local_idx]
                all_articles[global_idx]['clusterId'] = cluster_id
                all_articles[global_idx]['is_representative'] = 1 if i == best_local_idx else 0

    print(f"--- 군집화 완료. 총 {total_clusters}개의 이슈 그룹 생성 ---")

    # 새로 수집된 기사만 반환
    return all_articles[len(recent_db_articles):]