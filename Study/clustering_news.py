import torch
from sentence_transformers import SentenceTransformer, util
import uuid

# 5. 뉴스 군집화 (Clustering), 다소 다소 길어져서 별도 파일로 분리



# SentenceTransformer 모델 로드 (스크립트 시작 시 한 번만 로드)
# GPU가 있으면 'cuda', 없으면 'cpu'를 자동으로 사용합니다.
device = 'cuda' if torch.cuda.is_available() else 'cpu'
sbert_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2', device=device)




def cluster_news(recent_db_articles, processed_articles_for_db, threshold=0.75):
    all_articles_for_clustering = recent_db_articles + processed_articles_for_db     # 새로 수집된 기사와 DB의 최신 기사를 합쳐서 군집화 수행
    corpus = [f"{article['title']}. {article.get('description', '')}" for article in all_articles_for_clustering]
    # SBERT 모델을 사용하여 문장들을 임베딩(벡터화)
    embeddings = sbert_model.encode(corpus, convert_to_tensor=True, show_progress_bar=False)

    # 코사인 유사도 기반으로 임계값 이상의 유사도를 가진 기사 군집 탐색
    clusters = util.community_detection(embeddings, min_community_size=1, threshold=threshold)

    cluster_id_map = {}
    representative_map = {} # 대표 기사 인덱스를 기록하기 위한 맵

    # 각 군집에 대해 고유 ID 부여 및 대표 기사 설정
    for cluster in clusters:
        # 군집의 대표 ID로 짧고 고유한 UUID를 생성합니다.
        cluster_id = uuid.uuid4().hex

            # 군집의 첫 번째 기사를 대표로 지정합니다.
        representative_idx = cluster[0]
        representative_map[representative_idx] = 1

        for article_idx in cluster:
            # 맵에 '기사 인덱스' -> 'UUID clusterId' 저장
            cluster_id_map[article_idx] = cluster_id

    # 새로 수집된 기사들에 대해서만 cluster_id와 is_representative를 할당
    start_index_for_new_articles = len(recent_db_articles)
    for i, article in enumerate(processed_articles_for_db):
        # 전체 목록에서의 인덱스 계산
        combined_list_index = start_index_for_new_articles + i

            # 해당 인덱스의 기사가 속한 군집의 ID를 가져옴
        cluster_id = cluster_id_map.get(combined_list_index)

        if cluster_id:
            article['clusterId'] = cluster_id
            # 대표 기사 맵을 확인하여 대표 여부를 설정합니다.
            article['is_representative'] = 1 if representative_map.get(combined_list_index) else 0
        else:
            # 군집에 속하지 않은 경우, 자기 자신을 대표로 설정하고 새로운 UUID를 부여합니다.
            article['clusterId'] = uuid.uuid4().hex
            article['is_representative'] = 1
    print(f"--- 군집화 완료. 총 {len(clusters)}개의 군집을 찾았습니다. ---")