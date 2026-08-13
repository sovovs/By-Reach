"""Every approved primary-to-byCLI fallback chain is exercised explicitly."""

from unittest.mock import patch

from by_reach.channels import v2ex as v2ex_module
from by_reach.channels import xueqiu as xueqiu_module
from by_reach.channels.bilibili import BilibiliChannel
from by_reach.channels.reddit import RedditChannel
from by_reach.channels.twitter import TwitterChannel
from by_reach.channels.v2ex import V2EXChannel
from by_reach.channels.xueqiu import XueqiuChannel
from by_reach.channels.youtube import YouTubeChannel
from by_reach.probe import ProbeResult


def test_twitter_primary_success_does_not_call_bycli():
    channel = TwitterChannel()
    with patch.object(
        channel, "_check_twitter_cli", return_value=("ok", "twitter ready")
    ), patch.object(channel, "_check_bycli") as fallback:
        status, _ = channel.check()

    assert status == "ok"
    assert channel.active_backend == "twitter-cli"
    fallback.assert_not_called()


def test_twitter_primary_failure_calls_bycli_once():
    channel = TwitterChannel()
    with patch.object(channel, "_check_twitter_cli", return_value=None), patch.object(
        channel, "_check_bycli", return_value=("ok", "byCLI ready")
    ) as fallback:
        status, _ = channel.check()

    assert status == "ok"
    assert channel.active_backend == "bycli"
    fallback.assert_called_once_with()


def test_reddit_primary_success_does_not_call_bycli():
    channel = RedditChannel()
    with patch.object(channel, "_check_rdt", return_value=("ok", "rdt ready")), patch.object(
        channel, "_check_bycli"
    ) as fallback:
        status, _ = channel.check()

    assert status == "ok"
    assert channel.active_backend == "rdt-cli"
    fallback.assert_not_called()


def test_reddit_primary_failure_calls_bycli_once():
    channel = RedditChannel()
    with patch.object(channel, "_check_rdt", return_value=("warn", "rdt unavailable")), patch.object(
        channel, "_check_bycli", return_value=("ok", "byCLI ready")
    ) as fallback:
        status, _ = channel.check()

    assert status == "ok"
    assert channel.active_backend == "bycli"
    fallback.assert_called_once_with()


def test_bilibili_primary_success_does_not_call_bycli():
    channel = BilibiliChannel()
    with patch.object(channel, "_check_bili_cli", return_value=("ok", "bili ready")), patch.object(
        channel, "_check_bycli"
    ) as fallback:
        status, _ = channel.check()

    assert status == "ok"
    assert channel.active_backend == "bili-cli"
    fallback.assert_not_called()


def test_bilibili_primary_failure_calls_bycli_once():
    channel = BilibiliChannel()
    with patch.object(channel, "_check_bili_cli", return_value=("error", "broken")), patch.object(
        channel, "_check_bycli", return_value=("ok", "byCLI ready")
    ) as fallback:
        status, _ = channel.check()

    assert status == "ok"
    assert channel.active_backend == "bycli"
    fallback.assert_called_once_with()


def test_youtube_primary_success_does_not_call_bycli(monkeypatch):
    channel = YouTubeChannel()
    monkeypatch.setattr(
        "by_reach.channels.youtube.probe_command", lambda *_args, **_kwargs: ProbeResult("ok")
    )
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/deno" if name == "deno" else None)
    with patch.object(channel, "_check_bycli") as fallback:
        status, _ = channel.check()

    assert status == "ok"
    assert channel.active_backend == "yt-dlp"
    fallback.assert_not_called()


def test_youtube_primary_failure_calls_bycli_once(monkeypatch):
    channel = YouTubeChannel()
    monkeypatch.setattr(
        "by_reach.channels.youtube.probe_command", lambda *_args, **_kwargs: ProbeResult("missing")
    )
    with patch.object(channel, "_check_bycli", return_value=("ok", "byCLI ready")) as fallback:
        status, _ = channel.check()

    assert status == "ok"
    assert channel.active_backend == "bycli"
    fallback.assert_called_once_with()


def test_v2ex_primary_success_does_not_call_bycli():
    channel = V2EXChannel()
    with patch.object(v2ex_module, "_get_json", return_value=[{"id": 1}]), patch.object(
        channel, "_check_bycli"
    ) as fallback:
        status, _ = channel.check()

    assert status == "ok"
    assert channel.active_backend == "V2EX API"
    fallback.assert_not_called()


def test_v2ex_primary_failure_calls_bycli_once():
    channel = V2EXChannel()
    with patch.object(v2ex_module, "_get_json", side_effect=OSError("offline")), patch.object(
        channel, "_check_bycli", return_value=("ok", "byCLI ready")
    ) as fallback:
        status, _ = channel.check()

    assert status == "ok"
    assert channel.active_backend == "bycli"
    fallback.assert_called_once_with()


def test_xueqiu_primary_success_does_not_call_bycli():
    channel = XueqiuChannel()
    with patch.object(
        xueqiu_module,
        "_get_json",
        return_value={"data": {"quote": {"symbol": "SH601138"}}},
    ), patch.object(channel, "_check_bycli") as fallback:
        status, _ = channel.check()

    assert status == "ok"
    assert channel.active_backend == "Xueqiu API"
    fallback.assert_not_called()


def test_xueqiu_primary_failure_calls_bycli_once():
    channel = XueqiuChannel()
    with patch.object(xueqiu_module, "_get_json", side_effect=OSError("offline")), patch.object(
        channel, "_check_bycli", return_value=("ok", "byCLI ready")
    ) as fallback:
        status, _ = channel.check()

    assert status == "ok"
    assert channel.active_backend == "bycli"
    fallback.assert_called_once_with()
