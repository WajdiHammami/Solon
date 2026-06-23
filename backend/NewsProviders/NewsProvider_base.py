from abc import ABC, abstractmethod
from backend.models import Article

class NewsProvider(ABC):

    @abstractmethod
    def fetch_articles(self, query: str) -> list[Article]:
        pass

    @abstractmethod
    def extract_content(self, article: Article) -> str:
        pass

