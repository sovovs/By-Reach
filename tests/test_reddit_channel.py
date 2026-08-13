"""Reddit uses rdt-cli credentials before the declared byCLI fallback."""

import json
import time
from unittest.mock import patch

import pytest

from by_reach.channels.reddit import RedditChannel


def test_saved_rdt_credentials_are_primary_without_running_rdt(isolated_home):
    path = isolated_home / ".config" / "rdt-cli" / "credential.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"cookies": {"reddit_session": "explicit"}, "saved_at": time.time()}))
    with patch("shutil.which", return_value="/usr/local/bin/rdt"), patch(
        "subprocess.run",
        side_effect=AssertionError("rdt status must not run"),
    ), patch.object(RedditChannel, "_check_bycli", side_effect=AssertionError("no fallback")):
        channel = RedditChannel()
        status, _ = channel.check()
    assert status == "ok"
    assert channel.active_backend == "rdt-cli"


def test_reddit_falls_back_to_bycli_when_rdt_is_missing():
    channel = RedditChannel()
    with patch.object(channel, "_check_rdt", return_value=None), patch.object(
        channel, "_check_bycli", return_value=("ok", "byCLI ready")
    ):
        status, message = channel.check()
    assert (status, message, channel.active_backend) == ("ok", "byCLI ready", "bycli")


def test_reddit_stale_active_backend_clears_when_capability_is_missing():
    channel = RedditChannel()
    channel.active_backend = "bycli"
    with patch.object(channel, "_check_rdt", return_value=None), patch.object(
        channel, "_check_bycli", return_value=("off", "unavailable")
    ):
        status, _ = channel.check()
    assert status == "off"
    assert channel.active_backend is None


def test_rdt_missing_credential_is_reported_without_running_upstream():
    """Doctor never starts rdt because it can refresh browser credentials."""
    with patch("shutil.which", return_value="/usr/local/bin/rdt"), patch(
        "subprocess.run",
        side_effect=AssertionError("rdt status must not run"),
    ):
        status, message = RedditChannel()._check_rdt()

    assert status == "warn"
    assert "Cookie-Editor" in message


def test_rdt_malformed_credential_is_safe_warning(isolated_home):
    path = isolated_home / ".config" / "rdt-cli" / "credential.json"
    path.parent.mkdir(parents=True)
    path.write_text("not json", encoding="utf-8")

    with patch("shutil.which", return_value="/usr/local/bin/rdt"), patch(
        "subprocess.run",
        side_effect=AssertionError("rdt status must not run"),
    ):
        status, message = RedditChannel()._check_rdt()

    assert status == "warn"
    assert "无法安全解析" in message


def test_rdt_stale_credential_is_not_refreshed_or_rewritten(isolated_home):
    path = isolated_home / ".config" / "rdt-cli" / "credential.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "cookies": {"reddit_session": "explicit"},
                "saved_at": time.time() - 8 * 86400,
            }
        ),
        encoding="utf-8",
    )
    original = path.read_bytes()

    with patch("shutil.which", return_value="/usr/local/bin/rdt"), patch(
        "subprocess.run",
        side_effect=AssertionError("rdt status must not run"),
    ):
        status, message = RedditChannel()._check_rdt()

    assert status == "warn"
    assert "超过 7 天" in message
    assert path.read_bytes() == original


def test_rdt_credential_reader_refuses_a_symlink(isolated_home):
    victim = isolated_home / "victim.json"
    victim.write_text('{"cookies": {"reddit_session": "secret"}}', encoding="utf-8")
    path = isolated_home / ".config" / "rdt-cli" / "credential.json"
    path.parent.mkdir(parents=True)
    try:
        path.symlink_to(victim)
    except OSError:
        pytest.skip("symlinks are not supported on this platform")

    with patch("shutil.which", return_value="/usr/local/bin/rdt"):
        status, message = RedditChannel()._check_rdt()

    assert status == "warn"
    assert "符号链接" in message


def test_rdt_credential_reader_refuses_an_ancestor_symlink(isolated_home):
    victim_dir = isolated_home / "victim-config"
    credential_path = victim_dir / "rdt-cli" / "credential.json"
    credential_path.parent.mkdir(parents=True)
    credential_path.write_text(
        '{"cookies": {"reddit_session": "secret"}}', encoding="utf-8"
    )
    config_dir = isolated_home / ".config"
    try:
        config_dir.symlink_to(victim_dir, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are not supported on this platform")

    with patch("shutil.which", return_value="/usr/local/bin/rdt"):
        status, message = RedditChannel()._check_rdt()

    assert status == "warn"
    assert "符号链接" in message
