from langgraph.graph.state import CompiledStateGraph, Runnable, RunnableConfig
from langgraph.types import Send
from backend.Summarization.pipelineState import PipelineState, SummarizeState, BiasDetectionState
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
        self.graph_batch_summarization = self._build_graph_batch_summarization()
        self.graph_singular_summarization = self._build_graph_singular_summarization()
    

    def _build_graph_singular_summarization(self) -> CompiledStateGraph:
        graph = StateGraph(SummarizeState)
        graph.add_node("summarize_article", self._summarize_singular_article_node)
        graph.add_node("bias_detection", self._bias_detection_singular_node)

        graph.add_edge(START, "summarize_article")
        graph.add_conditional_edges("summarize_article", self._bias_detection_switch, ["bias_detection", END])

        return graph.compile()


    def _build_graph_batch_summarization(self) -> CompiledStateGraph:
        graph = StateGraph(PipelineState)

        graph.add_node("summarize_article", self._summarize_article_node)
        graph.add_node("synthesize", self._synthesize_node)
        graph.add_node("bias_detection", self._bias_detection_node)


        graph.add_conditional_edges(START,
                                    self._fan_out,
                                    ["summarize_article", "bias_detection"])

        graph.add_edge("summarize_article", "synthesize")
        graph.add_edge("bias_detection", "synthesize")
        graph.add_edge("synthesize", END)

        return graph.compile()


    def _fan_out(self, state: PipelineState) -> str:
        sends = []
        for article in state['articles']:
            sends.append(Send("summarize_article", SummarizeState(article=article)))
            sends.append(Send("bias_detection", BiasDetectionState(article=article)))
        return sends

    def _bias_detection_node(self, state: BiasDetectionState) -> Runnable:
        prompt = f"""You are a news analyst.
        You are given an article. Detect any potential bias in the article's content, framing, or language.
        Provide a brief explanation of any bias you identify.\n
        Start your response with "Bias Detected:" if you find bias, or "No Bias Detected." if you do not find any bias. Bias should be max 2 words set inside [] brackets. Explanation should be max 2 sentences.
        """


        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content=f"Article: {state['article'].title}\nSource: {state['article'].source_name}\nContent: {state['article'].content}\nURL={state['article'].url}")
        ]
        response = self.llm.invoke(messages)
        
        #extracting bias from the response: take tag after Bias detected it should be inside [] brackets

        bias = response.content.split("Bias Detected:")[-1].split("[")[-1].split("]")[0].strip() if "Bias Detected:" in response.content else "No Bias"
        explanation = response.content.split("Bias Detected:")[-1].split("]")[-1].strip() if "Bias Detected:" in response.content else "No bias detected."
        return {"tags": {state['article'].id: (bias, explanation)}}
        

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

    def _bias_detection_switch(self, state: PipelineState, config: RunnableConfig):
        if config["configurable"].get("enable_bias", True):
           return "bias_detection"
        else:
            return END 

    def _summarize_singular_article_node(self, state: SummarizeState) -> Runnable:
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
        article.summary = response.content
        return {"article": article}

    def _bias_detection_singular_node(self, state: SummarizeState) -> Runnable:
        prompt = f"""You are a news analyst.
        You are given an article. Detect any potential bias in the article's content, framing, or language.
        Provide a brief explanation of any bias you identify.\n
        Start your response with "Bias Detected:" if you find bias, or "No Bias Detected." if you do not find any bias. Bias should be max 2 words set inside [] brackets. Explanation should be max 2 sentences.
        """

        article = state['article']

        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content=f"Article: {state['article'].title}\nSource: {state['article'].source_name}\nContent: {state['article'].content}\nURL={state['article'].url}")
        ]
        response = self.llm.invoke(messages)
        
        #extracting bias from the response: take tag after Bias detected it should be inside [] brackets

        bias = response.content.split("Bias Detected:")[-1].split("[")[-1].split("]")[0].strip() if "Bias Detected:" in response.content else "No Bias"
        explanation = response.content.split("Bias Detected:")[-1].split("]")[-1].strip() if "Bias Detected:" in response.content else "No bias detected."

        article.tag = bias

        return {"article": article}
      

    def run_batch_summarization(self, articles: list[Article]) -> PipelineState:
        return self.graph_batch_summarization.invoke({"articles": articles, "summaries": [], "synthesis": ""})
    
    def run_singular_summarization(self, article: Article, config: dict) -> Article:
        return self.graph_singular_summarization.invoke({"article": article}, config={"configurable": config})