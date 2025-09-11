from Search_yesterday_news import get_yesterday_news
import google.generativeai as genai

def analyze_news(news_items):
    print(f"어제 뉴스 개수: {len(news_items)}")
    for item in news_items[:5]:  # 앞 5개만 예시로 출력
        print(item.get('title'))

if __name__ == "__main__":
    news_items = get_yesterday_news()
    analyze_news(news_items)