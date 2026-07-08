from backend.NewsProviders.NewsProvider_base import NewsProvider
from backend.models import Article
from newsapi import NewsApiClient
from newspaper import Article as NewspaperArticle

class NewsAPIProvider(NewsProvider):
    def __init__(self, api_key: str):
        self.newsapi = NewsApiClient(api_key=api_key)

    def fetch_articles(self, query: str | list[str], sources: list[str] = [], language: str = "en", sort_by: str = "relevancy", page_size: int = 5, page: int = 1) -> list[Article]:
        if isinstance(query, str):
            query = [query]
        articles = []
        responses = []
        for q in query:
            responses.append(self.newsapi.get_everything(q=q, sources=",".join(sources), language=language, sort_by=sort_by, page_size=page_size, page=page))
        for response in responses:
            if response["status"] == "ok":
                for i, article in enumerate(response["articles"]):
                    articles.append(Article(
                        id=i,
                        title=article["title"],
                        url=article["url"],
                        source_name=article["source"]["name"],
                        published_at=article["publishedAt"])
                    )
                
            else:
                print(f"Error fetching articles: {response['message']}")
        return articles

    def extract_content(self, url:str, return_content: bool = True) -> str:
        try:
            
            newspaper_article = NewspaperArticle(url)
            newspaper_article.download()
            newspaper_article.parse()
            if return_content:
                return newspaper_article.text
        except Exception as e:
            print(f"Error extracting content from {url}: {e}")
            return ""
