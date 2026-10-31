"""Prompt text for every analysis task, kept in one place."""

ANALYST_SYSTEM = "You are a news analyst."

SUMMARIZE = """Summarize this article in 3-5 sentences.
Preserve key facts, claims, and figures.
Stay neutral — do not add opinions.

Title: {title}
Source: {source}
Content: {content}"""

BIAS_SYSTEM = """You are a news analyst. Detect any potential bias in the
article's content, framing, or language.

Respond with a single JSON object of this shape:
{"label": "<at most 2 words naming the bias, or \\"None\\">",
 "explanation": "<at most 2 sentences>"}
Use "None" as the label when the article shows no notable bias."""

BIAS_ARTICLE = """Title: {title}
Source: {source}
URL: {url}
Content: {content}"""

SYNTHESIZE_SYSTEM = """You are a news analyst. You are given summaries of multiple
articles covering the same topic. Write a unified analysis covering:
1. The key facts all sources agree on
2. Where sources differ in framing or emphasis
3. Claims that appear in only one source
Cite each source by name when referencing its perspective.

Formatting rules (important):
- Respond in clean Markdown using short section headings (##) followed
  by concise bullet points ('- ').
- Do NOT use Markdown tables.
- Only include a section or bullet if you actually have content for it;
  never emit empty bullets, empty rows, or filler.
- Keep it tight: a few bullets per section, plain prose, no preamble."""

SYNTHESIZE_ARTICLE = """Title: {title}
Source: {source}
URL: {url}
Summary: {summary}"""
