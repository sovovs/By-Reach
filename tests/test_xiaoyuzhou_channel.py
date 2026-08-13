"""Xiaoyuzhou readiness keeps ffmpeg, script, and credential boundaries explicit."""

from pathlib import Path
from unittest.mock import Mock

from by_reach.channels import xiaoyuzhou as xiaoyuzhou_module
from by_reach.channels.xiaoyuzhou import XiaoyuzhouChannel
from by_reach.probe import ProbeResult


def _transcribe_script(home):
    path = Path(home) / ".by-reach" / "tools" / "xiaoyuzhou" / "transcribe.sh"
    path.parent.mkdir(parents=True)
    path.write_text("#!/bin/sh\n", encoding="utf-8")


def test_xiaoyuzhou_requires_ffmpeg(monkeypatch):
    monkeypatch.setattr(
        xiaoyuzhou_module,
        "probe_command",
        lambda *_args, **_kwargs: ProbeResult("missing"),
    )

    status, message = XiaoyuzhouChannel().check()

    assert status == "off"
    assert "ffmpeg" in message


def test_xiaoyuzhou_broken_ffmpeg_reports_recovery(monkeypatch):
    monkeypatch.setattr(
        xiaoyuzhou_module,
        "probe_command",
        lambda *_args, **_kwargs: ProbeResult("broken"),
    )

    status, message = XiaoyuzhouChannel().check()

    assert status == "error"
    assert "brew install ffmpeg" in message


def test_xiaoyuzhou_requires_the_managed_script(isolated_home, monkeypatch):
    monkeypatch.setattr(
        xiaoyuzhou_module,
        "probe_command",
        lambda *_args, **_kwargs: ProbeResult("ok"),
    )

    status, message = XiaoyuzhouChannel().check()

    assert status == "off"
    assert "转录脚本未安装" in message


def test_xiaoyuzhou_configured_path_activates_groq_whisper(
    isolated_home, monkeypatch
):
    _transcribe_script(isolated_home)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(
        xiaoyuzhou_module,
        "probe_command",
        lambda *_args, **_kwargs: ProbeResult("ok"),
    )
    config = Mock()
    config.get.return_value = "saved-groq-key"
    channel = XiaoyuzhouChannel()

    status, _ = channel.check(config)

    assert status == "ok"
    assert channel.active_backend == "groq-whisper"


def test_xiaoyuzhou_routes_only_its_public_host():
    channel = XiaoyuzhouChannel()

    assert channel.can_handle("https://www.xiaoyuzhoufm.com/episode/123")
    assert not channel.can_handle("https://notxiaoyuzhoufm.com/episode/123")
