from backend.config import NEWSAPI_KEY, set_env_variables
from backend.NewsProviders.NewsAPIProvider import NewsAPIProvider

def test_news_api_provider():
    set_env_variables()
    provider = NewsAPIProvider(api_key=NEWSAPI_KEY)
    articles = provider.fetch_articles(query="technology", sources=["techcrunch"])
    print(articles)
    assert isinstance(articles, list)
    assert len(articles) > 0
    for article in articles:
        assert hasattr(article, "title")
        assert hasattr(article, "url")
        assert hasattr(article, "source_name")
        assert hasattr(article, "published_at")



if __name__ == "__main__":
    test_news_api_provider()