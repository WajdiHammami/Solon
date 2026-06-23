from backend.NewsProviders.NewsProvider_base import NewsProvider
from backend.models import Article
from newsapi import NewsApiClient
from newspaper import Article as NewspaperArticle 

class NewsAPIProvider(NewsProvider):
    def __init__(self, api_key: str):
       self.newsapi = NewsApiClient(api_key=api_key)
     
    
    def fetch_articles(self, query: str | list[str], sources: list[str] = [], language: str = "en", sort_by:str = "relevancy", page_size: int=5, page: int=1) -> list[Article]:
        # Implement the logic to fetch articles from NewsAPI
        if isinstance(query, str):
            query = [query]
        articles = []
        responses = []
        for q in query:
            responses.append(self.newsapi.get_everything(q=q, sources=",".join(sources), language=language, sort_by=sort_by, page_size=page_size, page=page))
        for response in responses:
            if response["status"] == "ok":
                for article in response["articles"]:
                    articles.append(Article(
                        title=article["title"],
                        url=article["url"],
                        source_name=article["source"]["name"],
                        published_at=article["publishedAt"])
                        )
            else:
                print(f"Error fetching articles: {response['message']}")
        return articles

    def extract_content(self, article: Article, return_content: bool = True) -> str:
        try:
            if article.content:
                return article.content
            else:
                newspaper_article = NewspaperArticle(article.url)
                newspaper_article.download()
                newspaper_article.parse()
                article.content = newspaper_article.text
                if return_content:
                    return newspaper_article.text
        except Exception as e:
            print(f"Error extracting content from {article.url}: {e}")
            return ""
