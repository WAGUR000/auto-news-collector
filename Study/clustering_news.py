import torch
from sentence_transformers import SentenceTransformer, util
import uuid
from collections import defaultdict

# [개선 1] 한국어 성능이 훨씬 뛰어난 모델로 변경
# jhgan/ko-sroberta-multitask 모델이 한국어 뉴스 클러스터링에 SOTA급 성능을 보여줍니다.
MODEL_NAME = 'jhgan/ko-sroberta-multitask'
device = 'cuda' if torch.cuda.is_available() else 'cpu'
sbert_model = SentenceTransformer(MODEL_NAME, device=device)

def cluster_news(recent_db_articles, processed_articles_for_db, threshold=0.65):
    # 1. 전체 기사 병합 및 초기화
    all_articles = recent_db_articles + processed_articles_for_db
    for article in all_articles:
        article['clusterId'] = uuid.uuid4().hex
        article['is_representative'] = 1 # 기본값 설정

    # 2. [개선 2] 카테고리별로 기사 분류 (정확도 향상 핵심)
    # 정치 기사는 정치 기사끼리만 비교해야 엉뚱한 군집 생성을 막을 수 있습니다.
    articles_by_category = defaultdict(list)
    for idx, article in enumerate(all_articles):
        # 카테고리가 없는 경우 'Etc'로 분류
        cat = article.get('main_category', 'Etc')
        articles_by_category[cat].append((idx, article))

    total_clusters_found = 0

    print(f"--- 군집화 시작 (모델: {MODEL_NAME}, 임계값: {threshold}) ---")

    # 3. 각 카테고리별로 별도 군집화 수행
    for category, items in articles_by_category.items():
        if not items: continue
        
        # (원래 리스트에서의 인덱스, 기사 객체)
        original_indices = [item[0] for item in items]
        category_articles = [item[1] for item in items]

        # [개선 3] 임베딩 텍스트 최적화
        # '대분류: 정치' 같은 메타데이터는 제거하고, 제목과 본문 앞부분만 사용
        # 제목 가중치를 높이기 위해 제목을 두 번 넣거나 앞에 배치하는 전략 사용
        corpus = [
            f"{a['title']} {a['title']} {a.get('description', '')[:50]}" 
            for a in category_articles
        ]

        # 임베딩 생성
        embeddings = sbert_model.encode(corpus, convert_to_tensor=True, show_progress_bar=False)

        # 군집화 수행 (Fast Clustering)
        # min_community_size=2: 최소 2개 이상 모여야 군집으로 인정
        clusters = util.community_detection(embeddings, min_community_size=2, threshold=threshold)
        
        total_clusters_found += len(clusters)

        # 결과 반영
        for cluster in clusters:
            # 새 군집 ID 생성
            cluster_id = uuid.uuid4().hex
            
            # 대표 기사 선정 (Centroid 방식)
            cluster_embeddings = embeddings[cluster]
            centroid = torch.mean(cluster_embeddings, dim=0)
            cos_scores = util.cos_sim(centroid, cluster_embeddings)[0]
            
            # 점수가 가장 높은(중심에 가까운) 기사의 로컬 인덱스
            best_idx_local = torch.argmax(cos_scores).item()
            
            for i, local_idx in enumerate(cluster):
                # category_articles 리스트 내의 인덱스 -> 전체 all_articles의 실제 인덱스로 변환
                global_idx = original_indices[local_idx]
                
                all_articles[global_idx]['clusterId'] = cluster_id
                # 대표 기사 여부 마킹
                all_articles[global_idx]['is_representative'] = 1 if i == best_idx_local else 0

    print(f"--- 군집화 완료. 총 {total_clusters_found}개의 이슈 그룹 생성 ---")

    # 새로 수집된 기사만 반환 (DB 업데이트용)
    start_index_for_new = len(recent_db_articles)
    return all_articles[start_index_for_new:]