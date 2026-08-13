"""Registry and policy-backed channel smoke tests."""

import pytest

from by_reach.channels import get_all_channels, get_channel
from by_reach.channels.base import Channel
from by_reach.channels.bilibili import BilibiliChannel
from by_reach.channels.facebook import FacebookChannel
from by_reach.channels.instagram import InstagramChannel
from by_reach.channels.xiaohongshu import XiaoHongShuChannel
from by_reach.executor_policy import POLICIES


def test_registry_contains_supported_channels():
    names = [channel.name for channel in get_all_channels()]
    assert {"web", "github", "twitter", "facebook", "instagram", "v2ex"} <= set(names)
    assert get_channel("not-exists") is None


def test_registry_resolves_named_channel_and_rejects_unknown_policy():
    assert get_channel("github").name == "github"

    class UnknownChannel(Channel):
        name = "unknown"

        def can_handle(self, url):
            return False

    with pytest.raises(KeyError, match="unknown executor policy"):
        _ = UnknownChannel().policy


@pytest.mark.parametrize("reserved_name", ["backends", "policy"])
def test_channels_cannot_shadow_policy_controlled_attributes(reserved_name):
    with pytest.raises(TypeError, match=reserved_name):
        type(
            "ShadowingChannel",
            (Channel,),
            {reserved_name: ["unapproved"], "can_handle": lambda self, url: False},
        )


def test_channels_serialize_their_immutable_public_policy():
    for channel in get_all_channels():
        assert channel.backends == [item.name for item in channel.policy.executors]
        assert type(channel).backends is Channel.backends
    assert get_channel("exa_search").policy is POLICIES["exa"]


@pytest.mark.parametrize(
    ("channel", "url"),
    [
        (FacebookChannel(), "https://www.facebook.com/zuck"),
        (InstagramChannel(), "https://instagram.com/openai"),
        (XiaoHongShuChannel(), "https://www.xiaohongshu.com/explore/123"),
    ],
)
def test_bycli_site_channels_route_supported_hosts(channel, url):
    assert channel.can_handle(url)


def test_bilibili_falls_back_to_bycli_after_primary_failure(monkeypatch):
    channel = BilibiliChannel()
    monkeypatch.setattr(channel, "_check_bili_cli", lambda: ("error", "broken"))
    monkeypatch.setattr(channel, "_check_bycli", lambda: ("ok", "byCLI ready"))
    status, message = channel.check()
    assert (status, message, channel.active_backend) == ("ok", "byCLI ready", "bycli")


def test_bilibili_keeps_approved_primary_when_healthy(monkeypatch):
    channel = BilibiliChannel()
    monkeypatch.setattr(channel, "_check_bili_cli", lambda: ("ok", "primary ready"))
    monkeypatch.setattr(channel, "_check_bycli", lambda: pytest.fail("no fallback"))
    status, message = channel.check()
    assert (status, message, channel.active_backend) == ("ok", "primary ready", "bili-cli")
