from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from by_reach.executor_policy import (
    POLICIES,
    ChannelPolicy,
    ExecutorKind,
    ExecutorSpec,
)

ROOT = Path(__file__).parents[1]
FORBIDDEN = ("Jina Reader", "r.jina.ai", "Web Reader", "OpenCLI")


def test_generic_web_policy_has_only_bycli():
    policy = POLICIES["web"]
    assert [item.name for item in policy.executors] == ["bycli"]
    assert policy.executors[0].capability == "web/read"
    assert policy.executors[0].terminal is True


def test_approved_primary_and_fallback_order():
    expected = {
        "web": ["bycli"],
        "twitter": ["twitter-cli", "bycli"],
        "reddit": ["rdt-cli", "bycli"],
        "bilibili": ["bili-cli", "bycli"],
        "facebook": ["bycli"],
        "instagram": ["bycli"],
        "linkedin": ["bycli"],
        "xiaohongshu": ["bycli"],
    }
    assert {
        name: [item.name for item in POLICIES[name].executors]
        for name in expected
    } == expected


def test_mcp_kind_is_allowlisted_and_exa_is_the_only_initial_mcp():
    assert ExecutorKind.MCP.value == "mcp"
    assert [
        executor.capability
        for policy in POLICIES.values()
        for executor in policy.executors
        if executor.kind is ExecutorKind.MCP
    ] == ["exa.web_search_exa"]


def test_registry_exactly_matches_the_approved_executor_specs():
    expected = {
        "web": [("bycli", ExecutorKind.BYCLI, "web/read", True)],
        "twitter": [
            ("twitter-cli", ExecutorKind.CLI, "twitter", False),
            ("bycli", ExecutorKind.BYCLI, "twitter/search", True),
        ],
        "reddit": [
            ("rdt-cli", ExecutorKind.CLI, "rdt", False),
            ("bycli", ExecutorKind.BYCLI, "reddit/search", True),
        ],
        "bilibili": [
            ("bili-cli", ExecutorKind.CLI, "bili", False),
            ("bycli", ExecutorKind.BYCLI, "bilibili/search", True),
        ],
        "facebook": [("bycli", ExecutorKind.BYCLI, "facebook/search", True)],
        "instagram": [("bycli", ExecutorKind.BYCLI, "instagram/search", True)],
        "linkedin": [("bycli", ExecutorKind.BYCLI, "linkedin/search", True)],
        "xiaohongshu": [
            ("bycli", ExecutorKind.BYCLI, "xiaohongshu/search", True)
        ],
        "github": [("gh CLI", ExecutorKind.CLI, "gh", True)],
        "youtube": [
            ("yt-dlp", ExecutorKind.CLI, "yt-dlp", False),
            ("bycli", ExecutorKind.BYCLI, "youtube/search", True),
        ],
        "rss": [("feedparser", ExecutorKind.LIBRARY, "rss/read", True)],
        "exa": [
            (
                "Exa via mcporter",
                ExecutorKind.MCP,
                "exa.web_search_exa",
                True,
            )
        ],
        "xiaoyuzhou": [
            (
                "transcription",
                ExecutorKind.LIBRARY,
                "audio/transcribe",
                True,
            )
        ],
        "v2ex": [
            ("V2EX API", ExecutorKind.API, "v2ex/api", False),
            ("bycli", ExecutorKind.BYCLI, "v2ex/hot", True),
        ],
        "xueqiu": [
            ("Xueqiu API", ExecutorKind.API, "xueqiu/api", False),
            ("bycli", ExecutorKind.BYCLI, "xueqiu/search", True),
        ],
    }
    actual = {
        channel: [
            (spec.name, spec.kind, spec.capability, spec.terminal)
            for spec in policy.executors
        ]
        for channel, policy in POLICIES.items()
    }

    assert {name: policy.channel for name, policy in POLICIES.items()} == {
        name: name for name in expected
    }
    assert actual == expected


def test_registry_keys_match_policy_channel_names():
    assert all(name == policy.channel for name, policy in POLICIES.items())


def test_registry_is_immutable():
    original = POLICIES["web"]
    try:
        with pytest.raises(TypeError):
            POLICIES["web"] = POLICIES["twitter"]
    finally:
        if POLICIES["web"] is not original:
            POLICIES["web"] = original


def test_policy_requires_at_least_one_executor():
    with pytest.raises(ValueError, match="empty requires at least one executor"):
        ChannelPolicy("empty", ())


def test_only_final_executor_may_be_terminal():
    terminal = ExecutorSpec("first", ExecutorKind.CLI, "first", terminal=True)
    fallback = ExecutorSpec("fallback", ExecutorKind.BYCLI, "fallback")

    with pytest.raises(ValueError, match="only the final executor may be terminal"):
        ChannelPolicy("invalid", (terminal, fallback))


@pytest.mark.parametrize(
    ("instance", "attribute"),
    [
        (POLICIES["web"], "channel"),
        (POLICIES["web"].executors[0], "name"),
    ],
)
def test_policy_instances_are_immutable(instance, attribute):
    with pytest.raises(FrozenInstanceError):
        setattr(instance, attribute, "other")


def test_runtime_sources_do_not_contain_forbidden_web_executors():
    source_paths = sorted((ROOT / "by_reach").rglob("*.py"))
    assert source_paths, "expected Python sources under by_reach/"

    violations = []
    for path in source_paths:
        relative_path = path.relative_to(ROOT).as_posix()
        path_text = relative_path.casefold()
        source_text = path.read_text(encoding="utf-8").casefold()
        violations.extend(
            (relative_path, marker)
            for marker in FORBIDDEN
            if marker.casefold() in path_text or marker.casefold() in source_text
        )
    assert not violations, f"forbidden executor references: {violations}"
