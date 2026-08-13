"""Twitter uses explicit credentials before the declared byCLI fallback."""

import os
from unittest.mock import Mock, patch

from by_reach.channels.twitter import TwitterChannel, twitter_cli_child_env


def _which(*present):
    return lambda name: f"/usr/local/bin/{name}" if name in present else None


def test_twitter_cli_credentials_win_without_reading_browser_cookies(monkeypatch):
    monkeypatch.setenv("TWITTER_AUTH_TOKEN", "auth")
    monkeypatch.setenv("TWITTER_CT0", "ct0")
    with patch("shutil.which", side_effect=_which("twitter")), patch.object(
        TwitterChannel, "_check_bycli", side_effect=AssertionError("no fallback")
    ):
        channel = TwitterChannel()
        status, _ = channel.check()
    assert status == "ok"
    assert channel.active_backend == "twitter-cli"


def test_twitter_falls_back_to_bycli_when_credentials_are_missing(monkeypatch):
    monkeypatch.delenv("TWITTER_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWITTER_CT0", raising=False)
    channel = TwitterChannel()
    with patch("shutil.which", return_value=None), patch.object(
        channel, "_check_bycli", return_value=("ok", "byCLI ready")
    ):
        status, message = channel.check()
    assert (status, message, channel.active_backend) == ("ok", "byCLI ready", "bycli")


def test_twitter_stale_active_backend_clears_when_all_paths_fail():
    channel = TwitterChannel()
    channel.active_backend = "twitter-cli"
    with patch.object(channel, "_check_twitter_cli", return_value=None), patch.object(
        channel, "_check_bycli", return_value=("off", "unavailable")
    ):
        status, _ = channel.check()
    assert status == "off"
    assert channel.active_backend is None


def test_child_env_keeps_existing_shell_credentials_authoritative(monkeypatch):
    config = Mock()
    config.get.side_effect = lambda key: {"twitter_auth_token": "saved-auth", "twitter_ct0": "saved-ct0"}.get(key)
    monkeypatch.setenv("TWITTER_AUTH_TOKEN", "shell-auth")
    monkeypatch.setenv("TWITTER_CT0", "shell-ct0")
    assert twitter_cli_child_env(config) == {}
    assert os.environ["TWITTER_AUTH_TOKEN"] == "shell-auth"


def test_twitter_without_credentials_never_runs_upstream_or_browser_fallback(
    monkeypatch,
):
    monkeypatch.delenv("TWITTER_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWITTER_CT0", raising=False)
    channel = TwitterChannel()
    with patch("shutil.which", side_effect=_which("twitter")), patch(
        "subprocess.run",
        side_effect=AssertionError("twitter status must not run"),
    ), patch.object(
        channel, "_check_bycli", return_value=("off", "byCLI unavailable")
    ) as fallback:
        status, message = channel.check()

    assert status == "warn"
    assert "Cookie-Editor" in message
    assert channel.active_backend is None
    fallback.assert_called_once_with()


def test_twitter_saved_config_is_used_only_for_the_child_environment(monkeypatch):
    config = Mock()
    config.get.side_effect = lambda key: {
        "twitter_auth_token": "saved-auth",
        "twitter_ct0": "saved-ct0",
    }.get(key)
    monkeypatch.delenv("TWITTER_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWITTER_CT0", raising=False)
    channel = TwitterChannel()

    with patch("shutil.which", side_effect=_which("twitter")), patch(
        "subprocess.run",
        side_effect=AssertionError("twitter status must not run"),
    ), patch.object(
        channel, "_check_bycli", side_effect=AssertionError("no fallback")
    ):
        status, message = channel.check(config)

    assert status == "ok"
    assert channel.active_backend == "twitter-cli"
    assert "不会执行" in message
    assert "TWITTER_AUTH_TOKEN" not in os.environ
    assert "TWITTER_CT0" not in os.environ
