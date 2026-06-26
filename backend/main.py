from fastapi import FastAPI
from backend.models import Article
from backend.models import SummarizeRequest, SummarizeResponse
from backend.Summarization.pipelineState import PipelineState, SummarizeState, BiasDetectionState
from backend.Summarization.summarization_pipeline import SummarizationPipeline
from backend.NewsProviders.NewsAPIProvider import NewsAPIProvider
from langchain_groq import ChatGroq
import backend.config
import os

app = FastAPI()
providers = []
backend.config.set_env_variables()
providers.append(NewsAPIProvider(api_key=os.getenv("NEWSAPI_KEY")))
LLM = ChatGroq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"))
summarizer = SummarizationPipeline(llm=LLM)

@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/feed")
def get_feed(topic: str = None, page_size=10, page=1) -> list[Article]:
    articles = []
    for provider in providers:
        articles += provider.fetch_articles(topic or "Top headlines", page_size=10)
    return articles


@app.post("/summarize")
def summarize(request: SummarizeRequest) -> SummarizeResponse | Article:
    if len(SummarizeRequest["Articles"]) > 1:
        json_response = summarizer.run_batch_summarization(request.articles)
        return SummarizeResponse(**{
            "summaries": json_response["summaries"],
            "synthesis": json_response["synthesis"],
            "tags": json_response["tags"]
        })
    else:
        json_response = summarizer.run_singular_summarization(request.articles[0], config={"enable_bias": True})
        request.articles[0] = json_response["Article"]
        return Article