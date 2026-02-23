import trafilatura
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


def fetch_article_content(url):
    """
    URL에서 본문과 대표 이미지 URL을 추출합니다.
    Returns: (body: str | None, image_url: str | None)
    """
    if not url:
        return None, None
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None, None

        body = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
            no_fallback=False,
        )

        image_url = None
        soup = BeautifulSoup(downloaded, "html.parser")
        og_image = soup.find("meta", property="og:image")
        if og_image:
            image_url = og_image.get("content")

        return body, image_url

    except Exception:
        return None, None


def crawl_articles(articles, max_workers=10):
    """
    기사 리스트의 originallink를 병렬 크롤링하여 body, image_url 필드를 추가합니다.
    - originallink가 없는 기사(네이버뉴스 원문)는 body=None, image_url=None으로 처리됩니다.
    - 크롤링 실패 시에도 파이프라인이 중단되지 않고 None으로 처리됩니다.
    """
    to_crawl = {
        i: article["originallink"]
        for i, article in enumerate(articles)
        if article.get("originallink")
    }
    print(f"--- 🌐 원문 크롤링 시작: 전체 {len(articles)}건 중 {len(to_crawl)}건 대상 ---")

    results = {i: (None, None) for i in range(len(articles))}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {
            executor.submit(fetch_article_content, url): idx
            for idx, url in to_crawl.items()
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception:
                results[idx] = (None, None)

    success_count = sum(1 for body, _ in results.values() if body)
    print(f"--- ✅ 크롤링 완료: {success_count}/{len(to_crawl)}건 본문 추출 성공 ---")

    for i, article in enumerate(articles):
        article["body"], article["image_url"] = results[i]

    return articles
