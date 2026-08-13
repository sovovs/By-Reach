"""Approved executor order for each supported channel."""

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping


class ExecutorKind(str, Enum):
    CLI = "cli"
    MCP = "mcp"
    API = "api"
    LIBRARY = "library"
    BYCLI = "bycli"


@dataclass(frozen=True)
class ExecutorSpec:
    name: str
    kind: ExecutorKind
    capability: str
    terminal: bool = False


@dataclass(frozen=True)
class ChannelPolicy:
    channel: str
    executors: tuple[ExecutorSpec, ...]

    def __post_init__(self) -> None:
        if not self.executors:
            raise ValueError(f"{self.channel} requires at least one executor")
        if any(item.terminal for item in self.executors[:-1]):
            raise ValueError("only the final executor may be terminal")


def cli(name: str, capability: str) -> ExecutorSpec:
    return ExecutorSpec(name, ExecutorKind.CLI, capability)


def api(name: str, capability: str, *, terminal: bool = False) -> ExecutorSpec:
    return ExecutorSpec(name, ExecutorKind.API, capability, terminal=terminal)


def library(
    name: str, capability: str, *, terminal: bool = True
) -> ExecutorSpec:
    return ExecutorSpec(name, ExecutorKind.LIBRARY, capability, terminal=terminal)


def bycli(capability: str) -> ExecutorSpec:
    return ExecutorSpec(
        "bycli", ExecutorKind.BYCLI, capability, terminal=True
    )


_POLICIES = {
    "web": ChannelPolicy("web", (bycli("web/read"),)),
    "twitter": ChannelPolicy(
        "twitter",
        (cli("twitter-cli", "twitter"), bycli("twitter/search")),
    ),
    "reddit": ChannelPolicy(
        "reddit", (cli("rdt-cli", "rdt"), bycli("reddit/search"))
    ),
    "bilibili": ChannelPolicy(
        "bilibili", (cli("bili-cli", "bili"), bycli("bilibili/search"))
    ),
    "facebook": ChannelPolicy("facebook", (bycli("facebook/search"),)),
    "instagram": ChannelPolicy("instagram", (bycli("instagram/search"),)),
    "linkedin": ChannelPolicy("linkedin", (bycli("linkedin/search"),)),
    "xiaohongshu": ChannelPolicy(
        "xiaohongshu", (bycli("xiaohongshu/search"),)
    ),
    "github": ChannelPolicy(
        "github",
        (
            ExecutorSpec(
                "gh CLI", ExecutorKind.CLI, "gh", terminal=True
            ),
        ),
    ),
    "youtube": ChannelPolicy(
        "youtube", (cli("yt-dlp", "yt-dlp"), bycli("youtube/search"))
    ),
    "rss": ChannelPolicy("rss", (library("feedparser", "rss/read"),)),
    "exa": ChannelPolicy(
        "exa",
        (
            ExecutorSpec(
                "Exa via mcporter",
                ExecutorKind.MCP,
                "exa.web_search_exa",
                terminal=True,
            ),
        ),
    ),
    "xiaoyuzhou": ChannelPolicy(
        "xiaoyuzhou", (library("transcription", "audio/transcribe"),)
    ),
    "v2ex": ChannelPolicy(
        "v2ex", (api("V2EX API", "v2ex/api"), bycli("v2ex/hot"))
    ),
    "xueqiu": ChannelPolicy(
        "xueqiu",
        (api("Xueqiu API", "xueqiu/api"), bycli("xueqiu/search")),
    ),
}

for _policy_name, _policy in _POLICIES.items():
    if _policy_name != _policy.channel:
        raise ValueError(
            f"policy key {_policy_name!r} does not match channel "
            f"{_policy.channel!r}"
        )

POLICIES: Mapping[str, ChannelPolicy] = MappingProxyType(_POLICIES)
