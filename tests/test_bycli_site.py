"""Shared byCLI site helper requires exactly the declared read capability."""

from unittest.mock import patch

from by_reach.bycli import ByCliCapabilities, ByCliUnavailableError
from by_reach.channels.facebook import FacebookChannel


def _capabilities(*commands):
    return ByCliCapabilities.from_json(
        "[" + ",".join(
            f'{{"command":"{command}","access":"read"}}' for command in commands
        ) + "]"
    )


def test_site_channel_marks_bycli_active_only_for_its_read_capability():
    channel = FacebookChannel()
    with patch("by_reach.channels._bycli_site.probe_bycli_capabilities", return_value=_capabilities("facebook/search")):
        status, _ = channel.check()
    assert status == "ok"
    assert channel.active_backend == "bycli"


def test_site_channel_clears_stale_backend_for_missing_capability():
    channel = FacebookChannel()
    channel.active_backend = "bycli"
    with patch("by_reach.channels._bycli_site.probe_bycli_capabilities", return_value=_capabilities("facebook/write")):
        status, _ = channel.check()
    assert status == "off"
    assert channel.active_backend is None


def test_site_channel_bounds_probe_error():
    with patch("by_reach.channels._bycli_site.probe_bycli_capabilities", side_effect=ByCliUnavailableError("x" * 1000)):
        status, message = FacebookChannel().check()
    assert status == "off"
    assert len(message) < 500
