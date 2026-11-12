"""Tests for the external-agreement evaluation (evaluation/ package).

Everything is offline: a fake news provider, the scripted LLM, synthetic data.
"""

import json
import math
import random

import pytest

from backend.models import Article
from backend.news_providers.base import NewsProviderError
from backend.tests.conftest import ScriptedLLM
from evaluation import collect as collect_mod
from evaluation import report, stats
from evaluation.files import Outlet, load_outlets, read_jsonl
from evaluation.run_bias import leaks_outlet, run_condition

LONG = "Body text about the policy debate. " * 30  # above MIN_CONTENT_CHARS


@pytest.fixture(autouse=True)
def no_retry_waits(monkeypatch):
    """Retry backoff is real time; tests must not sleep."""
    from evaluation import config as eval_config

    monkeypatch.setattr(eval_config, "RETRY_DELAYS", (0, 0))


# --- stats -----------------------------------------------------------------------


class TestStats:
    def test_rankdata_averages_ties(self):
        assert stats.rankdata([10, 20, 20, 30]) == [1, 2.5, 2.5, 4]

    def test_spearman_monotonic_and_reversed(self):
        assert stats.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1)
        assert stats.spearman([1, 2, 3, 4], [9, 7, 3, 1]) == pytest.approx(-1)

    def test_spearman_with_ties_matches_reference(self):
        # Ranks: x -> [1, 2.5, 2.5, 4, 5], y -> [1, 3, 2, 4.5, 4.5]; deviations
        # from the mean rank 3 give sxy = 9, sxx = syy = 9.5, so rho = 9 / 9.5.
        x, y = [1, 2, 2, 3, 4], [1, 3, 2, 4, 4]
        assert stats.spearman(x, y) == pytest.approx(9 / 9.5)

    def test_constant_series_has_no_correlation(self):
        assert math.isnan(stats.spearman([1, 1, 1], [1, 2, 3]))

    def test_bootstrap_is_deterministic_and_brackets_estimate(self):
        values = [random.Random(1).uniform(-1, 1) for _ in range(40)]
        a = stats.bootstrap_ci(stats.mean, values, 500, seed=3)
        b = stats.bootstrap_ci(stats.mean, values, 500, seed=3)
        assert a == b and a[0] <= stats.mean(values) <= a[1]

    def test_to_class_rounds_and_clamps(self):
        assert [stats.to_class(v) for v in (-3.0, -1.5, -0.4, 0.5, 2.7)] == [-2, -1, 0, 1, 2]

    def test_agreement_and_baselines(self):
        assert stats.agreement([0, 1, -2], [0, 2, 0]) == {"exact": 1 / 3, "within_one": 2 / 3, "n": 3}
        # Edge classes have 2 neighbours-or-self, middle ones 3.
        assert stats.random_baseline([-2, 0])["within_one"] == pytest.approx((2 / 5 + 3 / 5) / 2)

    def test_confusion_rows_are_actual(self):
        matrix = stats.confusion([1], [-1])
        assert matrix[1][3] == 1 and sum(map(sum, matrix)) == 1


# --- outlets.csv -----------------------------------------------------------------


def test_outlets_csv_ratings_are_cited():
    from evaluation import config

    outlets = load_outlets(config.OUTLETS_CSV)
    assert len(outlets) >= 10
    assert len({o.domain for o in outlets}) == len(outlets)
    # Every rating must cite the page it was read from and when.
    for o in outlets:
        assert (o.allsides_rating == "") == (o.allsides_accessed == "") == (o.allsides_url == "")
        assert (o.adfontes_bias is None) == (o.adfontes_accessed == "") == (o.adfontes_url == "")
        if o.allsides_rating:
            # A category name, or a Bias Meter score within AllSides' range.
            if o.allsides_rating.lower() not in config.ALLSIDES_SCALE:
                lo, hi = config.ALLSIDES_SCORE_RANGE
                assert lo <= float(o.allsides_rating) <= hi, o.name
            assert o.allsides_url.startswith("https://www.allsides.com/"), o.name
        if o.adfontes_bias is not None:
            assert -42 <= o.adfontes_bias <= 42
            assert "adfontesmedia.com" in o.adfontes_url


# --- collect ---------------------------------------------------------------------


class FakeNews:
    def __init__(self, fail_after: int | None = None):
        self.calls = []
        self.fail_after = fail_after

    def fetch_articles(self, query, page_size=5, page=1, *, domains=None, **_):
        if self.fail_after is not None and len(self.calls) >= self.fail_after:
            raise NewsProviderError("NewsAPI error: rateLimited")
        self.calls.append((query, domains))
        domain = domains[0]
        return [
            Article(id=i, title=f"{domain} story {i} on {query[:5]}", url=f"https://{domain}/{query[:5]}/{i}",
                    source_name=domain, published_at="2026-11-01T00:00:00Z")
            for i in range(2)
        ]

    def extract_content(self, url):
        return "" if url.endswith("/1") else LONG


OUTLETS = [Outlet("Left Daily", "left.example"), Outlet("Right Daily", "right.example")]
TOPICS = {"immigration": "immigration", "guns": "guns"}


def test_collect_writes_dataset_and_marks_usable(tmp_path):
    news = FakeNews()
    summary = collect_mod.collect(news, OUTLETS, TOPICS, tmp_path / "d.jsonl", tmp_path / "s.json", workers=2)
    records = read_jsonl(tmp_path / "d.jsonl")
    assert summary == {"requests": 4, "new_articles": 8, "stopped_reason": None}
    assert {r["outlet"] for r in records} == {"left.example", "right.example"}
    assert sum(r["usable"] for r in records) == 4  # "/1" articles scraped empty
    assert news.calls[0][1] == ["left.example"]  # restricted by domain


def test_collect_stops_on_quota_and_resumes(tmp_path):
    paths = (tmp_path / "d.jsonl", tmp_path / "s.json")
    first = collect_mod.collect(FakeNews(fail_after=3), OUTLETS, TOPICS, *paths, workers=1)
    assert first["requests"] == 3 and "rateLimited" in first["stopped_reason"]

    resumed = FakeNews()
    second = collect_mod.collect(resumed, OUTLETS, TOPICS, *paths, workers=1)
    assert second["requests"] == 1  # only the unfinished pair
    urls = [r["url"] for r in read_jsonl(paths[0])]
    assert len(urls) == len(set(urls)) == 8


def test_probe_reports_coverage_and_scrapability():
    results = collect_mod.probe(FakeNews(), OUTLETS, "immigration")
    assert results == [
        {"domain": "left.example", "found": 2, "scrapable": 1},
        {"domain": "right.example", "found": 2, "scrapable": 1},
    ]


def test_probe_stops_on_provider_error():
    results = collect_mod.probe(FakeNews(fail_after=1), OUTLETS, "immigration")
    assert results[0]["found"] == 2 and "rateLimited" in results[1]["error"]


def test_collect_respects_request_limit(tmp_path):
    summary = collect_mod.collect(FakeNews(), OUTLETS, TOPICS, tmp_path / "d.jsonl", tmp_path / "s.json",
                                  max_requests=1, workers=1)
    assert summary["requests"] == 1 and "limit" in summary["stopped_reason"]


# --- run_bias --------------------------------------------------------------------


def _record(outlet, i, lean_hint="", title=None):
    return {
        "url": f"https://{outlet}/a{i}", "outlet": outlet, "outlet_name": outlet.split(".")[0].title(),
        "source_name": outlet.split(".")[0].title(), "topic": "guns",
        "title": title or f"Story {i}", "published_at": "2026-11-01T00:00:00Z",
        "content": LONG + lean_hint, "usable": True,
    }


class LeanLLM(ScriptedLLM):
    """Leans left for 'left' text, right otherwise; reputation from the outlet name."""

    def invoke(self, request):
        self.requests.append(request)
        body = request.messages[1].content
        if request.messages[0].content.startswith("You are a media analyst"):
            content = json.dumps({"lean": -2 if "Left" in body else 2})
        else:
            lean = -1 if "progressive" in body else 1
            content = json.dumps({"label": "x", "explanation": "e", "political": True, "lean": lean})
        from backend.llm.models import GenerationResponse
        return GenerationResponse(content=content, model="lean-llm")


@pytest.mark.anyio
async def test_run_conditions_and_resume(tmp_path):
    dataset = [_record("left.example", i, " progressive") for i in range(3)]
    dataset += [_record("right.example", i) for i in range(3)]
    llm = LeanLLM()
    for condition in ("blinded", "unblinded", "reputation"):
        summary = await run_condition(llm, condition, dataset, OUTLETS, tmp_path, concurrency=2)
        assert summary["errors"] == 0
    blinded = read_jsonl(tmp_path / "blinded.jsonl")
    assert len(blinded) == 6 and {r["lean"] for r in blinded} == {-1, 1}
    assert {r["outlet"]: r["lean"] for r in read_jsonl(tmp_path / "reputation.jsonl")} == {
        "left.example": -2, "right.example": 2}

    calls = len(llm.requests)
    again = await run_condition(llm, "blinded", dataset, OUTLETS, tmp_path)
    assert again["processed"] == 0 and len(llm.requests) == calls  # resumable


@pytest.mark.anyio
async def test_unblinded_sees_source_and_blinded_does_not(tmp_path):
    dataset = [_record("left.example", 0, title="Story - Left")]
    llm = LeanLLM()
    await run_condition(llm, "blinded", dataset, OUTLETS, tmp_path)
    await run_condition(llm, "unblinded", dataset, OUTLETS, tmp_path)
    blinded_prompt, unblinded_prompt = (r.messages[1].content for r in llm.requests)
    assert "left.example" not in blinded_prompt.lower() and "Source:" not in blinded_prompt
    assert "Source: Left" in unblinded_prompt and "https://left.example/a0" in unblinded_prompt


@pytest.mark.anyio
async def test_failed_items_are_recorded_and_retried(tmp_path):
    dataset = [_record("left.example", 0)]
    bad = ScriptedLLM(bias_reply="not json")
    first = await run_condition(bad, "blinded", dataset, OUTLETS, tmp_path)
    assert first["errors"] == 1
    retry = await run_condition(LeanLLM(), "blinded", dataset, OUTLETS, tmp_path)
    assert retry["processed"] == 1 and retry["errors"] == 0


def test_leak_check_flags_names_the_blinding_missed():
    record = _record("left.example", 0)
    assert not leaks_outlet(record)
    # Syndicated copy: NewsAPI's source and URL are an aggregator's, so blinding
    # (which only knows those) can't strip the original outlet's name.
    record.update(source_name="Some Aggregator", url="https://aggregator.example/a0",
                  outlet_name="Left Daily", content=LONG + " Left Daily reporters found...")
    assert leaks_outlet(record)


# --- report ----------------------------------------------------------------------


def _synthetic(n_outlets=6, per_outlet=6):
    ratings = ["Left", "Lean Left", "Center", "Center", "Lean Right", "Right"]
    outlets, dataset, blinded, unblinded, reputation = [], [], [], [], []
    for k in range(n_outlets):
        domain = f"o{k}.example"
        outlets.append(Outlet(
            name=f"O{k}", domain=domain,
            allsides_rating=ratings[k], allsides_accessed="2026-11-12",
            allsides_url="https://www.allsides.com/x",
            adfontes_bias=float(k * 8 - 20), adfontes_accessed="2026-11-12",
            adfontes_url="https://adfontesmedia.com/x",
        ))
        true = report.config.ALLSIDES_SCALE[ratings[k].lower()]
        for i in range(per_outlet):
            url = f"https://{domain}/{i}"
            dataset.append({"url": url, "outlet": domain, "usable": True})
            lean = max(-2, min(2, true + (1 if i == 0 else 0)))
            blinded.append({"url": url, "outlet": domain, "political": True, "lean": lean, "leak": False})
            unblinded.append({"url": url, "outlet": domain, "political": True, "lean": true})
        reputation.append({"outlet": domain, "lean": true})
    # A non-political article and an error must be ignored.
    blinded.append({"url": "x", "outlet": "o0.example", "political": False, "lean": None})
    blinded.append({"url": "y", "outlet": "o0.example", "error": "boom"})
    return outlets, dataset, {"blinded": blinded, "unblinded": unblinded, "reputation": reputation}


def test_report_end_to_end_on_synthetic_data():
    outlets, dataset, runs = _synthetic()
    r = report.build_report(outlets, dataset, runs, min_articles=5)
    assert r["blinded"]["allsides"]["n"] == 6
    assert r["blinded"]["allsides"]["spearman"] > 0.9
    assert r["blinded"]["allsides"]["exact"] == pytest.approx(1.0)
    assert r["baselines"]["always_center"]["exact"] == pytest.approx(2 / 6)
    assert r["baselines"]["reputation_only"]["allsides"]["spearman"] == pytest.approx(1.0)
    assert r["blinding_effect"]["outlets"] == 6
    assert r["errors"]["blinded"] == 1 and r["leak_rate"] == 0
    markdown = report.render_markdown(r)
    assert "Spearman" in markdown and "O5" in markdown
    json.dumps(report._json_safe(r))  # serializable, NaN-free


def test_report_excludes_thin_outlets():
    outlets, dataset, runs = _synthetic(per_outlet=3)
    r = report.build_report(outlets, dataset, runs, min_articles=5)
    assert r["outlets_included"] == [] and len(r["outlets_excluded"]) == 6
    assert math.isnan(r["blinded"]["allsides"]["spearman"])
    assert "excluded" in report.render_markdown(r)


@pytest.mark.anyio
async def test_retryable_errors_are_retried(tmp_path):
    from backend.llm.errors import LLMRateLimitError

    class FlakyLLM(LeanLLM):
        failures = 2

        def invoke(self, request):
            if FlakyLLM.failures:
                FlakyLLM.failures -= 1
                raise LLMRateLimitError("slow down")
            return super().invoke(request)

    summary = await run_condition(FlakyLLM(), "blinded", [_record("left.example", 0)], OUTLETS, tmp_path)
    assert summary["errors"] == 0
    assert read_jsonl(tmp_path / "blinded.jsonl")[0]["lean"] == 1


@pytest.mark.anyio
async def test_non_retryable_errors_fail_fast(tmp_path):
    from backend.llm.errors import LLMAuthenticationError
    llm = ScriptedLLM(fail={("detect_bias", "*"): LLMAuthenticationError("bad key")})
    summary = await run_condition(llm, "blinded", [_record("left.example", 0)], OUTLETS, tmp_path)
    assert summary["errors"] == 1 and len(llm.requests) == 1  # no retries


def test_report_warns_when_models_are_mixed():
    outlets, dataset, runs = _synthetic()
    runs["blinded"][0]["model"] = "model-a"
    runs["blinded"][1]["model"] = "model-b"
    runs["blinded"][-1]["model"] = "model-c"  # the error row: not counted
    r = report.build_report(outlets, dataset, runs, min_articles=5)
    assert r["models"] == ["model-a", "model-b"]
    assert "more than one model" in report.render_markdown(r)



class TestAllSidesScores:
    @pytest.mark.parametrize("score, expected", [
        (-6.0, -2), (-3.0, -2), (-2.99, -1), (-1.0, -1), (-0.99, 0), (0.0, 0),
        (0.99, 0), (1.0, 1), (2.99, 1), (3.0, 2), (6.0, 2),
    ])
    def test_published_bands(self, score, expected):
        assert report.score_to_class(score) == expected

    def test_category_or_score(self):
        assert report.allsides_score(Outlet("a", "a", "Lean Left")) == -1
        assert report.allsides_class(Outlet("a", "a", "-4.3")) == -2
        assert report.allsides_score(Outlet("a", "a", "-4.3")) == -4.3
        assert report.allsides_score(Outlet("a", "a", "")) is None

    def test_numeric_scores_drive_correlation(self):
        outlets, dataset, runs = _synthetic()
        scores = ["-5", "-2", "-0.5", "0.5", "2", "5"]
        outlets = [Outlet(name=o.name, domain=o.domain, allsides_rating=s,
                          allsides_accessed="2026-11-12", allsides_url="https://www.allsides.com/x")
                   for o, s in zip(outlets, scores)]
        r = report.build_report(outlets, dataset, runs, min_articles=5)
        assert r["blinded"]["allsides"]["spearman"] > 0.9
        assert r["blinded"]["allsides"]["exact"] == pytest.approx(1.0)



def test_report_includes_reference_ceiling():
    outlets, dataset, runs = _synthetic()
    r = report.build_report(outlets, dataset, runs, min_articles=5)
    # Synthetic AllSides categories and Ad Fontes scores are both monotonic in k.
    assert r["reference_agreement"]["spearman"] > 0.9
    assert r["reference_agreement"]["n"] == 6
    assert "Reference ceiling" in report.render_markdown(r)
