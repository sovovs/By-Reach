# -*- coding: utf-8 -*-
"""Tests for doctor module."""

import hashlib
import json
import os
import shutil
import subprocess
from argparse import Namespace
from pathlib import Path

import pytest

import by_reach.doctor as doctor
from by_reach.config import Config
from by_reach.executor_runtime import ExecutionResult


class _StubChannel:
    def __init__(self, name, description, tier, status, message, backends=None,
                 active_backend=None):
        self.name = name
        self.description = description
        self.tier = tier
        self._status = status
        self._message = message
        self.backends = backends or []
        self.active_backend = active_backend

    def check(self, config=None):
        return self._status, self._message


@pytest.fixture
def tmp_config(tmp_path):
    return Config(config_path=tmp_path / "config.yaml")


class TestDoctor:
    def test_check_all_collects_channel_results(self, tmp_config, monkeypatch):
        monkeypatch.setattr(
            doctor,
            "get_all_channels",
            lambda: [
                _StubChannel("web", "网页", 0, "ok", "可抓取网页", ["requests"],
                             active_backend="requests"),
                _StubChannel("github", "GitHub", 0, "warn", "gh 未安装", ["gh"]),
                _StubChannel("exa_search", "全网语义搜索", 1, "off", "mcporter 未配置", ["Exa"]),
            ],
        )

        results = doctor.check_all(tmp_config)

        assert results == {
            "web": {
                "status": "ok",
                "name": "网页",
                "message": "可抓取网页",
                "tier": 0,
                "backends": ["requests"],
                "active_backend": "requests",
                "active_probe_backend": None,
                "probe_status": None,
            },
            "github": {
                "status": "warn",
                "name": "GitHub",
                "message": "gh 未安装",
                "tier": 0,
                "backends": ["gh"],
                "active_backend": None,
                "active_probe_backend": None,
                "probe_status": None,
            },
            "exa_search": {
                "status": "off",
                "name": "全网语义搜索",
                "message": "mcporter 未配置",
                "tier": 1,
                "backends": ["Exa"],
                "active_backend": None,
                "active_probe_backend": None,
                "probe_status": None,
            },
        }

    def test_real_web_channel_reports_confirmed_bycli_capability_as_active(
        self, monkeypatch
    ):
        from by_reach.channels.web import WebChannel

        calls = []

        def runner(args, timeout=None):
            calls.append((list(args), timeout))
            return ExecutionResult(
                0,
                json.dumps(
                    [
                        {
                            "command": "web/read",
                            "access": "read",
                            "site": "web",
                        }
                    ]
                ),
                "",
            )

        channel = WebChannel(runner=runner)
        monkeypatch.setattr(doctor, "get_all_channels", lambda: [channel])

        result = doctor.check_all(config=None)["web"]

        assert result["backends"] == ["bycli"]
        assert result["active_backend"] == "bycli"
        assert result["active_probe_backend"] is None
        assert result["probe_status"] is None
        assert calls == [(["bycli", "list", "-f", "json"], 10)]

    @pytest.mark.parametrize(
        ("name", "backend"), [("github", "gh CLI"), ("youtube", "yt-dlp")]
    )
    def test_approved_active_backend_is_not_reported_as_probe(
        self, monkeypatch, name, backend
    ):
        channel = _StubChannel(
            name,
            name,
            0,
            "ok",
            "healthy",
            [backend],
            active_backend=backend,
        )
        monkeypatch.setattr(doctor, "get_all_channels", lambda: [channel])

        result = doctor.check_all(config=None)[name]

        assert result["active_backend"] == backend
        assert result["active_probe_backend"] is None
        assert result["probe_status"] is None

    def test_format_report(self):
        report = doctor.format_report(
            {
                "web": {
                    "status": "ok",
                    "name": "网页",
                    "message": "可抓取网页",
                    "tier": 0,
                    "backends": ["requests"],
                },
                "exa_search": {
                    "status": "off",
                    "name": "全网语义搜索",
                    "message": "mcporter 未配置",
                    "tier": 1,
                    "backends": ["Exa"],
                },
                "xiaohongshu": {
                    "status": "warn",
                    "name": "小红书",
                    "message": "MCP 已配置，但健康检查超时",
                    "tier": 2,
                    "backends": ["mcporter"],
                },
            }
        )

        # Strip Rich markup tags for assertion (PR #170 added [bold], [yellow] etc.)
        import re
        plain = re.sub(r"\[[^\]]*\]", "", report)
        assert "By-Reach" in plain
        assert "装好即用：" in plain
        assert "1/3 个渠道可用" in plain
        # Inactive optional channels should be summarized in one line
        assert "可选渠道可以解锁" in plain


def test_stale_active_backend_does_not_leak_into_errored_result(monkeypatch):
    """渠道单例上一轮的 active_backend 不得泄漏进本轮异常结果(Codex review 发现)。"""
    from by_reach import doctor

    class _ExplodingChannel:
        name = "boom"
        description = "爆炸渠道"
        tier = 0
        backends = ["a", "b"]
        active_backend = "a"  # 上一轮成功的残留

        def check(self, config=None):
            raise RuntimeError("boom")

    monkeypatch.setattr(doctor, "get_all_channels", lambda: [_ExplodingChannel()])
    results = doctor.check_all(config=None)
    assert results["boom"]["status"] == "error"
    assert results["boom"]["active_backend"] is None
    assert results["boom"]["active_probe_backend"] is None
    assert results["boom"]["probe_status"] is None


def test_channel_exception_credentials_are_scrubbed(monkeypatch):
    """Doctor is the final trust boundary for unexpected channel errors."""

    class _ExplodingChannel:
        name = "secret"
        description = "敏感渠道"
        tier = 0
        backends = ["secret-backend"]
        active_backend = None

        def check(self, config=None):
            raise RuntimeError(
                "request https://alice:password@example.test/data"
                "?access_token=top-secret failed"
            )

    monkeypatch.setattr(doctor, "get_all_channels", lambda: [_ExplodingChannel()])

    message = doctor.check_all(config=None)["secret"]["message"]

    assert "alice" not in message
    assert "password" not in message
    assert "top-secret" not in message
    assert "https://***@example.test/data?access_token=***" in message


def test_channel_success_message_credentials_are_scrubbed(monkeypatch):
    """Expected channel messages must pass through the same trust boundary."""
    channel = _StubChannel(
        "configured",
        "已配置渠道",
        0,
        "warn",
        (
            "upstream returned https://alice:password@example.test/data"
            "?api_key=top-secret"
        ),
        ["upstream"],
    )
    monkeypatch.setattr(doctor, "get_all_channels", lambda: [channel])

    message = doctor.check_all(config=None)["configured"]["message"]

    assert "alice" not in message
    assert "password" not in message
    assert "top-secret" not in message
    assert "https://***@example.test/data?api_key=***" in message


def _snapshot_user_roots() -> tuple:
    entries = []
    seen = set()
    for variable in (
        "HOME",
        "USERPROFILE",
        "XDG_CONFIG_HOME",
        "APPDATA",
        "LOCALAPPDATA",
    ):
        root = Path(os.environ[variable])
        if root in seen:
            continue
        seen.add(root)
        if not root.exists():
            entries.append((variable, ".", "missing"))
            continue
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                detail = ("symlink", os.readlink(path))
            elif path.is_dir():
                detail = ("directory", path.stat().st_mode & 0o777)
            elif path.is_file():
                detail = (
                    "file",
                    path.stat().st_mode & 0o777,
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                )
            else:
                detail = ("other",)
            entries.append((variable, relative, detail))
    return tuple(entries)


def test_real_doctor_path_is_zero_write_and_never_runs_risky_status_commands(
    monkeypatch, tmp_path, capsys
):
    """Run the real Doctor collector with deterministic external probes."""
    import by_reach.channels.v2ex as v2ex
    import by_reach.channels.xueqiu as xueqiu
    from by_reach import cli

    workdir = tmp_path / "empty-workdir"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    monkeypatch.delenv("MCPORTER_CONFIG", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    available = {
        "gh",
        "yt-dlp",
        "bili",
        "ffmpeg",
        "mcporter",
        "twitter",
        "rdt",
        "deno",
        "node",
    }
    monkeypatch.setattr(
        shutil,
        "which",
        lambda name: f"/audit-bin/{name}" if name in available else None,
    )

    calls = []

    def fake_run(command, **kwargs):
        argv = [str(item) for item in command]
        calls.append(argv)
        name = Path(argv[0]).name
        assert name != "mcporter"
        assert argv[1:] not in (
            ["auth", "status"],
            ["status"],
            ["daemon", "status"],
        )
        if name == "gh":
            assert argv[1:] == ["--version"]
            assert kwargs["env"]["GH_TELEMETRY"] == "false"
            assert kwargs["env"]["DO_NOT_TRACK"] == "true"
            output = "gh version 2.92.0"
        elif name == "yt-dlp":
            output = "2026.01.01"
        elif name == "bili":
            output = "0.3.0"
        elif name == "ffmpeg":
            output = "ffmpeg version 7.0"
        elif name == "bycli":
            assert argv[1:] == ["list", "-f", "json"]
            assert kwargs["shell"] is False
            output = json.dumps(
                [
                    {
                        "command": command,
                        "access": "read",
                        "site": "web",
                    }
                    for command in ("web/read", "twitter/search", "reddit/search", "bilibili/search", "facebook/search", "instagram/search", "linkedin/search", "xiaohongshu/search", "youtube/search", "v2ex/hot", "xueqiu/search")
                ]
            )
        else:
            pytest.fail(f"unexpected Doctor subprocess: {argv}")
        return subprocess.CompletedProcess(argv, 0, output, "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(v2ex, "_get_json", lambda _url: [])
    monkeypatch.setattr(
        xueqiu,
        "_get_json",
        lambda _url, _config=None: {
            "data": {"quote": {"symbol": "SH601138"}}
        },
    )

    before = _snapshot_user_roots()
    cli._cmd_doctor(Namespace(json=True))
    after = _snapshot_user_roots()

    assert after == before
    assert calls
    assert all(Path(call[0]).name != "mcporter" for call in calls)
    payload = json.loads(capsys.readouterr().out)
    assert payload["github"]["status"] == "warn"
    assert payload["github"]["active_backend"] is None
    assert payload["web"]["status"] == "ok"
    assert payload["web"]["active_backend"] == "bycli"
    assert ["bycli", "list", "-f", "json"] in calls
    for channel_name in (
        "twitter",
        "reddit",
        "facebook",
        "instagram",
        "xiaohongshu",
    ):
        assert payload[channel_name]["status"] == "ok"
        assert payload[channel_name]["active_backend"] == "bycli"
