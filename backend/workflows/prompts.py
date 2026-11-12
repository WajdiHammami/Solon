"""Prompt text for every analysis task, kept in one place."""

import hashlib

ANALYST_SYSTEM = "You are a news analyst."

SUMMARIZE = """Summarize this article in 3-5 sentences.
Preserve key facts, claims, and figures.
Stay neutral — do not add opinions.

Title: {title}
Source: {source}
Content: {content}"""

BIAS_SYSTEM = """You are a news analyst. Assess bias in the article's content,
framing, and language. You are not told which outlet published it: judge only
the text in front of you, never an outlet's reputation.

Respond with a single JSON object of this shape:
{"label": "<at most 2 words naming the bias, or \\"None\\">",
 "explanation": "<at most 2 sentences>",
 "political": <true or false>,
 "lean": <-2, -1, 0, 1, 2, or null>}

Rules:
- "label": use "None" when the article shows no notable bias.
- "political": true if the article is about politics, government, policy, or a
  politically contested issue; false otherwise (sports, technology,
  entertainment, science, business news without a policy angle, ...).
- "lean": where the article's framing sits on the US left-right spectrum:
  -2 Left, -1 Lean Left, 0 Center or balanced, 1 Lean Right, 2 Right.
  Base it on framing, word choice, which voices are quoted, and what is
  emphasized or omitted, not on the topic alone. Use null when "political"
  is false."""

BIAS_ARTICLE = """Title: {title}
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


def _version(*templates: str) -> str:
    return hashlib.sha256("\0".join(templates).encode("utf-8")).hexdigest()[:12]


# Derived from the prompt text, so editing a prompt automatically invalidates
# cached results it produced (see backend.storage.sql_cache). Summary and bias
# are versioned separately: changing one recomputes only that part.
SUMMARY_VERSION = _version(ANALYST_SYSTEM, SUMMARIZE)
BIAS_VERSION = _version(BIAS_SYSTEM, BIAS_ARTICLE)
