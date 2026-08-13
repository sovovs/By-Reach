"""Exa doctor checks only exact, local mcporter configuration facts."""

import json

import pytest

from by_reach.channels.exa_search import ExaSearchChannel


def _write_mcporter_config(tmp_path, payload):
    path = tmp_path / "config" / "mcporter.json"
    path.parent.mkdir()
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_exa_requires_mcporter(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _name: None)

    status, message = ExaSearchChannel().check()

    assert status == "off"
    assert "mcporter" in message


def test_exa_configured_exactly_is_unverified_without_starting_mcporter(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    _write_mcporter_config(
        tmp_path,
        {"mcpServers": {"exa": {"baseUrl": "https://mcp.exa.ai/mcp"}}, "imports": []},
    )
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/mcporter" if name == "mcporter" else None)
    monkeypatch.setattr(
        "subprocess.run",
        lambda *_args, **_kwargs: pytest.fail("Doctor must not execute mcporter"),
    )

    status, message = ExaSearchChannel().check()

    assert status == "warn"
    assert "不能仅凭配置宣称可用" in message


def test_exa_ignores_unrelated_metadata_and_isolates_imports(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _write_mcporter_config(
        tmp_path,
        {
            "mcpServers": {"unrelated": {"baseUrl": "https://example.test/exa-project"}},
            "imports": ["cursor"],
        },
    )
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/mcporter" if name == "mcporter" else None)

    status, message = ExaSearchChannel().check()

    assert status == "warn"
    assert "没有展开" in message


def test_exa_invalid_mcporter_config_is_an_error(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "config" / "mcporter.json"
    path.parent.mkdir()
    path.write_text("not-json", encoding="utf-8")
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/mcporter" if name == "mcporter" else None)

    status, message = ExaSearchChannel().check()

    assert status == "error"
    assert "JSON" in message
