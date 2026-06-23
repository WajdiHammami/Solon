from langgraph.graph.state import CompiledStateGraph, Runnable
from langgraph.types import Send
from backend.Summarization.pipelineState import PipelineState, SummarizeState
from langgraph.graph import (
    StateGraph,
     START,
    END
)
from langchain_core.messages import SystemMessage, HumanMessage
from backend.models import Article



class SummarizationPipeline:
    def __init__(self, llm):
        self.llm = llm
        self.graph = self._build_graph()
    
    def _build_graph(self) -> CompiledStateGraph:
        graph = StateGraph(PipelineState)

        graph.add_node("summarize_article", self._summarize_article_node)
        graph.add_node("synthesize", self._synthesize_node)

        graph.add_conditional_edges(START,
                                    self._fan_out,
                                    ["summarize_article"])

        graph.add_edge("summarize_article", "synthesize")
        graph.add_edge("synthesize", END)

        return graph.compile()


    def _fan_out(self, state: PipelineState) -> str:
        return [
            Send("summarize_article", {"article": article}) for article in state['articles']
        ]

    def _synthesize_node(self, state: PipelineState) -> Runnable:
        prompt = f"""You are a news analyst.
        You are given summaries of multiple articles covering the same topic.

        Write a unified analysis that:
        1. Identifies the key facts all sources agree on
        2. Highlights where sources differ in framing or emphasis
        3. Notes any claims that appear in only one source
        Cite each source by name when referencing its perspective.\n\n"""

        articles_text = "Articles: \n"
        for article, summary in zip(state['articles'], state['summaries']):
            articles_text += f"Article: {article.title}\nSource: {article.source_name}\nSummary: {summary}\nURL={article.url}\n\n"
        
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content=articles_text)
        ]
        response = self.llm.invoke(messages)
        return {"synthesis": response.content}
    


    def _summarize_article_node(self, state: SummarizeState) -> Runnable:
        article = state['article']
        messages = [
            SystemMessage(content="You are a news analyst."),
            HumanMessage(content=f"""Article: 
                         Title: {article.title}
                         Source: {article.source_name}
                         Content: {article.content})
                Summarize this article in 3-5 sentences.
                Preserve key facts, claims, and figures.
                Stay neutral — do not add opinions.""")      
        ]
        response = self.llm.invoke(messages)
        return {"summaries": [response.content]}

    def run(self, articles: list[Article]) -> PipelineState:
        return self.graph.invoke({"articles": articles, "summaries": [], "synthesis": ""})