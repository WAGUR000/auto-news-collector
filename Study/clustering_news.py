import torch
from sentence_transformers import SentenceTransformer, util
import uuid

# 5. 뉴스 군집화 (Clustering), 다소 다소 길어져서 별도 파일로 분리  
# SentenceTransformer 모델 로드 (스크립트 시작 시 한 번만 로드)
# GPU가 있으면 'cuda', 없으면 'cpu'를 자동으로 사용합니다.
device = 'cuda' if torch.cuda.is_available() else 'cpu'
sbert_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2', device=device)




def cluster_news(recent_db_articles, processed_articles_for_db, threshold=0.75):
    all_articles = recent_db_articles + processed_articles_for_db     # 새로 수집된 기사와 DB의 최신 기사를 합쳐서 군집화 수행
    corpus = [
        f"대분류: {a.get('main_category', '')}. 소분류: {a.get('sub_category', '')}. 제목: {a['title']}. {a.get('description', '')}"
        for a in all_articles
    ]
    # SBERT 모델을 사용하여 문장들을 임베딩(벡터화)
    embeddings = sbert_model.encode(corpus, convert_to_tensor=True, show_progress_bar=False)

    # 코사인 유사도 기반으로 임계값 이상의 유사도를 가진 기사 군집 탐색
    clusters = util.community_detection(embeddings, min_community_size=1, threshold=threshold)

    for article in all_articles:
        article['clusterId'] = uuid.uuid4().hex
        article['is_representative'] = 1

    #  탐지된 군집 정보로 덮어쓰기
    for cluster_indices in clusters:
        if len(cluster_indices) < 2:
            continue
        
        cluster_id = uuid.uuid4().hex
        
        # 군집의 중심점(Centroid)에 가장 가까운 기사를 대표로 선정
        cluster_embeddings = embeddings[cluster_indices]
        centroid = torch.mean(cluster_embeddings, dim=0)
        similarities = util.cos_sim(centroid, cluster_embeddings)
        representative_local_idx = torch.argmax(similarities).item()
        representative_global_idx = cluster_indices[representative_local_idx]

        for article_idx in cluster_indices:
            article = all_articles[article_idx]
            article['clusterId'] = cluster_id
            article['is_representative'] = 1 if article_idx == representative_global_idx else 0
            
    print(f"--- 군집화 완료. 총 {len(clusters)}개의 군집(유사 기사 그룹)을 찾았습니다. ---")

    #  군집화 정보가 추가된 '새로운 기사' 목록만 반환
    start_index_for_new = len(recent_db_articles)
    return all_articles[start_index_for_new:]