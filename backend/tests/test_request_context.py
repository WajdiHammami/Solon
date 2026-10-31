"""Tests for request-id log correlation."""

import logging

import pytest

from backend.request_context import (
    REQUEST_ID_HEADER,
    RequestIdFilter,
    get_request_id,
    resolve_request_id,
)


class TestResolveRequestId:
    @pytest.mark.parametrize("incoming", ["abc123", "req-1_a.b", "x" * 64])
    def test_reuses_safe_ids(self, incoming):
        assert resolve_request_id(incoming) == incoming

    @pytest.mark.parametrize(
        "incoming",
        [None, "", "x" * 65, "evil\nINFO fake log line", "a b", "<script>"],
    )
    def test_replaces_missing_or_unsafe_ids(self, incoming):
        resolved = resolve_request_id(incoming)
        assert resolved != incoming
        assert len(resolved) == 12 and resolved.isalnum()


def test_filter_defaults_outside_a_request():
    record = logging.LogRecord("backend", logging.INFO, __file__, 1, "msg", (), None)
    RequestIdFilter().filter(record)
    assert record.request_id == "-" == get_request_id()


class CapturingHandler(logging.Handler):
    """Collects (request_id, message) the way the real handlers see them."""

    def __init__(self):
        super().__init__()
        self.addFilter(RequestIdFilter())
        self.lines: list[tuple[str, str]] = []

    def emit(self, record):
        self.lines.append((record.request_id, record.getMessage()))


@pytest.fixture
def captured():
    handler = CapturingHandler()
    backend_logger = logging.getLogger("backend")
    previous_level = backend_logger.level
    backend_logger.addHandler(handler)
    backend_logger.setLevel(logging.INFO)
    yield handler
    backend_logger.removeHandler(handler)
    backend_logger.setLevel(previous_level)


def _payload(id):
    return {
        "id": id,
        "title": f"t{id}",
        "url": f"https://example.com/{id}",
        "source_name": "S",
        "published_at": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def client(make_client, issue):
    issue(_payload(1), _payload(2))
    return make_client()[0]


def test_response_carries_generated_id(client):
    resp = client.get("/health")
    assert len(resp.headers[REQUEST_ID_HEADER]) == 12


def test_response_echoes_safe_client_id(client):
    resp = client.get("/health", headers={REQUEST_ID_HEADER: "client-42"})
    assert resp.headers[REQUEST_ID_HEADER] == "client-42"


def test_unsafe_client_id_is_replaced(client):
    resp = client.get("/health", headers={REQUEST_ID_HEADER: "bad id!"})
    assert resp.headers[REQUEST_ID_HEADER] != "bad id!"


def test_workflow_logs_carry_the_request_id(client, captured):
    client.post(
        "/analyze",
        json={"articles": [_payload(1), _payload(2)]},
        headers={REQUEST_ID_HEADER: "batch-7"},
    )
    batch_lines = [(rid, msg) for rid, msg in captured.lines if "Batch" in msg]
    assert batch_lines, captured.lines
    assert all(rid == "batch-7" for rid, _ in batch_lines)
    assert ("batch-7", "POST /analyze -> 200") in [
        (rid, msg.split(" (")[0]) for rid, msg in captured.lines
    ]


def test_sync_endpoint_in_worker_thread_carries_the_id(client, captured):
    client.get(
        "/article/content",
        params={"url": "https://example.com/1"},
        headers={REQUEST_ID_HEADER: "content-1"},
    )
    extract_lines = [rid for rid, msg in captured.lines if msg.startswith("Extracted")]
    assert extract_lines == ["content-1"]


def test_each_request_keeps_its_own_id(client, captured):
    for rid in ("first", "second"):
        client.post(
            "/analyze/article", json=_payload(1), headers={REQUEST_ID_HEADER: rid}
        )
    request_lines = [rid for rid, msg in captured.lines if msg.startswith("POST")]
    assert request_lines == ["first", "second"]
    assert get_request_id() == "-"  # reset after each request
