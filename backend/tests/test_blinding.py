"""Tests for stripping the outlet's identity from text given to the bias model."""

from backend.workflows.blinding import PLACEHOLDER, blind, blind_title, outlet_aliases

URL = "https://www.nbcnews.com/politics/some-story"


def test_aliases_cover_name_variants_and_domain():
    aliases = outlet_aliases("The Washington Post", "https://www.washingtonpost.com/x")
    assert {"The Washington Post", "Washington Post", "washingtonpost.com", "washingtonpost"} <= set(aliases)
    assert aliases == sorted(aliases, key=len, reverse=True)  # longest replaced first


def test_replaces_name_domain_and_root_case_insensitively():
    text = "NBC News reported... Read more at nbcnews.com. Follow NBCNEWS on social."
    blinded = blind(text, "NBC News", URL)
    assert "nbc" not in blinded.lower()
    assert blinded.count(PLACEHOLDER) == 3


def test_name_without_leading_the():
    text = "According to Washington Post reporters, and The Washington Post itself..."
    blinded = blind(text, "The Washington Post", "https://www.washingtonpost.com/x")
    assert "Washington Post" not in blinded


def test_does_not_touch_words_that_merely_contain_a_name():
    # "Fox" alias must not hit "Foxconn"; "axios" root must not hit "axiosly" etc.
    assert blind("Foxconn shares rose.", "Fox", "https://www.fox.com/x") == "Foxconn shares rose."
    assert "Reuterson" in blind("Mr Reuterson said", "Reuters", "https://www.reuters.com/x")


def test_short_generic_roots_are_kept():
    # "abc" (from abc.com) is too short to strip safely on its own.
    assert "abc" not in outlet_aliases("Example", "https://abc.com/x")
    assert "the abc conjecture" in blind("the abc conjecture", "Example", "https://abc.com/x")


def test_title_drops_newsapi_source_suffix():
    title = "Senate passes budget - NBC News"
    assert blind_title(title, "NBC News", URL) == "Senate passes budget"


def test_empty_inputs():
    assert blind("plain text", "", "") == "plain text"
