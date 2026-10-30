"""Tests for ``backend.profile`` loading and validation."""

import json
from types import SimpleNamespace

from backend.models import Profile
from backend import profile as profile_module

VALID_PROFILE = {
    "sources": [{"name": "BBC", "url": "https://bbc.co.uk", "enabled": True}],
    "topics": ["tech", "AI"],
    "newsapi_enabled": True,
}


def test_load_profile_reads_configured_path(tmp_path, monkeypatch):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(VALID_PROFILE))
    monkeypatch.setattr(
        profile_module, "get_settings", lambda: SimpleNamespace(profile_path=str(path))
    )

    profile = profile_module.load_profile()
    assert isinstance(profile, Profile)
    assert profile.topics == ["tech", "AI"]
    assert profile.sources[0].name == "BBC"


def test_validate_profile_accepts_valid_data():
    assert isinstance(profile_module.validate_profile(VALID_PROFILE), Profile)


def test_validate_profile_rejects_invalid_data():
    assert profile_module.validate_profile({"sources": "not-a-list"}) is None


def test_bundled_default_profile_is_valid():
    """The shipped default profile must satisfy the schema."""
    from pathlib import Path

    default = Path(__file__).resolve().parents[1] / "profiles" / "default.json"
    data = json.loads(default.read_text())
    assert profile_module.validate_profile(data) is not None
