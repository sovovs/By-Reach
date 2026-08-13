"""Credential-bearing channels must reject lookalike or disguised hosts."""

import socket

import pytest

from by_reach.channels.bilibili import BilibiliChannel
from by_reach.channels.facebook import FacebookChannel
from by_reach.channels.github import GitHubChannel
from by_reach.channels.instagram import InstagramChannel
from by_reach.channels.linkedin import LinkedInChannel
from by_reach.channels.reddit import RedditChannel
from by_reach.channels.twitter import TwitterChannel
from by_reach.channels.v2ex import V2EXChannel
from by_reach.channels.xiaohongshu import XiaoHongShuChannel
from by_reach.channels.xiaoyuzhou import XiaoyuzhouChannel
from by_reach.channels.xueqiu import XueqiuChannel
from by_reach.channels.youtube import YouTubeChannel
from by_reach.utils.url import (
    host_matches,
    normalize_public_http_url,
    resolve_public_http_url,
)


@pytest.mark.parametrize(
    ("channel", "valid_url"),
    [
        (TwitterChannel(), "https://mobile.twitter.com/user/status/1"),
        (TwitterChannel(), "https://X.COM./user/status/1"),
        (XiaoHongShuChannel(), "https://www.xiaohongshu.com/explore/1"),
        (XiaoHongShuChannel(), "https://xhslink.com/a/1"),
        (BilibiliChannel(), "https://www.bilibili.com/video/BV1"),
        (BilibiliChannel(), "https://b23.tv/abc"),
        (XueqiuChannel(), "https://stock.xueqiu.com/v5/stock/quote"),
    ],
)
def test_credential_channels_accept_exact_hosts_and_subdomains(channel, valid_url):
    assert channel.can_handle(valid_url)


@pytest.mark.parametrize(
    ("channel", "malicious_url"),
    [
        (TwitterChannel(), "https://x.com.evil.test/user/status/1"),
        (TwitterChannel(), "https://notx.com/user/status/1"),
        (TwitterChannel(), "https://x.com@evil.test/user/status/1"),
        (TwitterChannel(), "https://user:pass@x.com/user/status/1"),
        (TwitterChannel(), "ftp://x.com/user/status/1"),
        (XiaoHongShuChannel(), "https://xiaohongshu.com.evil.test/explore/1"),
        (XiaoHongShuChannel(), "https://xiaohongshu.com@evil.test/explore/1"),
        (BilibiliChannel(), "https://bilibili.com.evil.test/video/BV1"),
        (BilibiliChannel(), "https://b23.tv@evil.test/abc"),
        (XueqiuChannel(), "https://xueqiu.com.evil.test/S/SH600519"),
        (XueqiuChannel(), "https://xueqiu.com@evil.test/S/SH600519"),
    ],
)
def test_credential_channels_reject_lookalikes_and_userinfo(channel, malicious_url):
    assert not channel.can_handle(malicious_url)


@pytest.mark.parametrize(
    ("channel", "subdomain_url", "port_url"),
    [
        (
            GitHubChannel(),
            "https://api.github.com/repos/openai/openai-python",
            "https://github.com:443/openai/openai-python",
        ),
        (
            YouTubeChannel(),
            "https://m.youtube.com/watch?v=abc",
            "https://youtu.be:443/abc",
        ),
        (
            RedditChannel(),
            "https://old.reddit.com/r/python",
            "https://reddit.com:443/r/python",
        ),
        (
            LinkedInChannel(),
            "https://www.linkedin.com/in/example",
            "https://linkedin.com:443/in/example",
        ),
        (
            V2EXChannel(),
            "https://www.v2ex.com/t/1",
            "https://v2ex.com:443/t/1",
        ),
        (
            XiaoyuzhouChannel(),
            "https://www.xiaoyuzhoufm.com/episode/1",
            "https://xiaoyuzhoufm.com:443/episode/1",
        ),
        (
            FacebookChannel(),
            "https://m.facebook.com/groups/1",
            "https://facebook.com:443/groups/1",
        ),
        (
            InstagramChannel(),
            "https://www.instagram.com/example",
            "https://instagram.com:443/example",
        ),
    ],
)
def test_fixed_domain_channels_accept_subdomains_and_explicit_ports(
    channel, subdomain_url, port_url
):
    assert channel.can_handle(subdomain_url)
    assert channel.can_handle(port_url)


@pytest.mark.parametrize(
    ("channel", "official_domain"),
    [
        (GitHubChannel(), "github.com"),
        (YouTubeChannel(), "youtube.com"),
        (RedditChannel(), "reddit.com"),
        (LinkedInChannel(), "linkedin.com"),
        (V2EXChannel(), "v2ex.com"),
        (XiaoyuzhouChannel(), "xiaoyuzhoufm.com"),
        (FacebookChannel(), "facebook.com"),
        (InstagramChannel(), "instagram.com"),
    ],
)
def test_fixed_domain_channels_reject_suffix_lookalikes_and_userinfo(
    channel, official_domain
):
    assert not channel.can_handle(f"https://{official_domain}.evil.test/path")
    assert not channel.can_handle(f"https://{official_domain}@evil.test/path")
    assert not channel.can_handle(f"https://user:pass@{official_domain}/path")


@pytest.mark.parametrize(
    "malicious_url",
    [
        "https://x.com:not-a-port/path",
        "https://x.com:65536/path",
        "https://x.com:-1/path",
        "https://x.com:999999999999/path",
    ],
)
def test_host_matches_rejects_invalid_ports(malicious_url):
    assert not host_matches(malicious_url, "x.com")


@pytest.mark.parametrize(
    "url",
    [
        "http://metadata.google.internal。/latest/meta-data",
        "http://LOCALHOST。/admin",
        "http://foo.internal。/admin",
        "http://foo。internal。/admin",
        "http://foo．internal．/admin",
        "http://foo｡internal｡/admin",
        "http://foo.internal．．/admin",
        "http://１２７。０。０。１/admin",
    ],
)
def test_public_url_normalization_blocks_unicode_dns_separator_ssrf(url):
    with pytest.raises(ValueError, match="public HTTP"):
        normalize_public_http_url(url)


def test_public_url_normalization_emits_ascii_idna_hostname():
    assert normalize_public_http_url("HTTPS://例子.测试。/路径?q=1") == (
        "https://xn--fsqu00a.xn--0zwm56d/路径?q=1"
    )


def test_public_url_normalization_uses_nontransitional_browser_idna():
    assert normalize_public_http_url("https://faß.de/path") == (
        "https://xn--fa-hia.de/path"
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://.example.com/path",
        "https://example..com/path",
        "https://-example.com/path",
        "https://example-.com/path",
    ],
)
def test_public_url_normalization_rejects_invalid_idna_dns_labels(url):
    with pytest.raises(ValueError, match="public HTTP"):
        normalize_public_http_url(url)


def _dns_answer(family, address, port=443):
    if family == socket.AF_INET6:
        sockaddr = (address, port, 0, 0)
    else:
        sockaddr = (address, port)
    return (family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", sockaddr)


@pytest.mark.parametrize(
    ("url", "answers"),
    [
        (
            "http://127.0.0.1.nip.io/private",
            [_dns_answer(socket.AF_INET, "127.0.0.1", 80)],
        ),
        (
            "https://mixed.example/path",
            [
                _dns_answer(socket.AF_INET, "93.184.216.34"),
                _dns_answer(socket.AF_INET, "10.0.0.1"),
            ],
        ),
        (
            "https://ipv6.example/path",
            [_dns_answer(socket.AF_INET6, "fd00::1")],
        ),
        ("https://empty.example/path", []),
        ("https://malformed.example/path", [(socket.AF_INET,)]),
        (
            "https://wrong-family.example/path",
            [_dns_answer(socket.AF_INET6, "93.184.216.34")],
        ),
    ],
)
def test_initial_dns_preflight_fails_closed_for_nonpublic_or_invalid_answers(
    url, answers
):
    def resolver(*_args, **_kwargs):
        return answers

    with pytest.raises(ValueError, match="public HTTP"):
        resolve_public_http_url(url, resolver=resolver)


def test_initial_dns_preflight_hides_resolver_errors():
    def resolver(*_args, **_kwargs):
        raise RuntimeError("resolver details TOPSECRET")

    with pytest.raises(ValueError, match="only public HTTP") as raised:
        resolve_public_http_url("https://example.com", resolver=resolver)

    assert "TOPSECRET" not in str(raised.value)


def test_initial_dns_preflight_accepts_all_global_answers_and_uses_ascii_host():
    calls = []

    def resolver(host, port, **kwargs):
        calls.append((host, port, kwargs))
        return [
            _dns_answer(socket.AF_INET, "93.184.216.34", port),
            _dns_answer(socket.AF_INET6, "2606:4700:4700::1111", port),
            _dns_answer(socket.AF_INET, "93.184.216.34", port),
        ]

    result = resolve_public_http_url("https://faß.de:8443/path", resolver=resolver)

    assert result == "https://xn--fa-hia.de:8443/path"
    assert calls == [
        ("xn--fa-hia.de", 8443, {"type": socket.SOCK_STREAM})
    ]


def test_initial_dns_preflight_does_not_resolve_public_ip_literals():
    def resolver(*_args, **_kwargs):
        pytest.fail("public IP literals must not use DNS")

    assert resolve_public_http_url(
        "https://[2606:4700:4700::1111]:443/path", resolver=resolver
    ) == "https://[2606:4700:4700::1111]:443/path"
