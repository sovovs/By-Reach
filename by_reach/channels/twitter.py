# -*- coding: utf-8 -*-
"""Twitter/X — explicit twitter-cli credentials, then byCLI."""

import os
import shutil

from by_reach.utils.url import host_matches

from ._bycli_site import ByCliSiteChannel


def twitter_cli_child_env(config=None) -> dict[str, str]:
    """Return saved credentials missing from the current process environment.

    The returned mapping is meant for a single child process.  Existing shell
    variables remain authoritative and ``os.environ`` is never mutated.
    """
    if config is None:
        return {}

    child_env = {}
    for env_name, config_key in (
        ("TWITTER_AUTH_TOKEN", "twitter_auth_token"),
        ("TWITTER_CT0", "twitter_ct0"),
    ):
        if env_name in os.environ:
            continue
        value = config.get(config_key)
        if value:
            child_env[env_name] = str(value)
    return child_env


class TwitterChannel(ByCliSiteChannel):
    name = "twitter"
    description = "Twitter/X 推文"
    capability = "twitter/search"
    tier = 1

    def can_handle(self, url: str) -> bool:
        return host_matches(url, "x.com", "twitter.com")

    def check(self, config=None):
        self.active_backend = None
        primary = self._check_twitter_cli(config)
        if primary is not None and primary[0] == "ok":
            self.active_backend = "twitter-cli"
            return primary
        fallback = self._check_bycli()
        if fallback[0] == "ok":
            self.active_backend = "bycli"
            return fallback
        self.active_backend = None
        if primary is not None:
            return primary
        return fallback

    def _check_twitter_cli(self, config=None):
        """Inspect explicit credentials without starting twitter-cli.

        Upstream ``twitter status`` automatically reads browser cookies when
        credentials are missing *or invalid*. Doctor cannot disable that
        fallback, so executing it would violate the Cookie-Editor-only policy.
        """
        if not shutil.which("twitter"):
            return None

        child_env = twitter_cli_child_env(config)
        auth_token = os.environ.get("TWITTER_AUTH_TOKEN") or child_env.get(
            "TWITTER_AUTH_TOKEN"
        )
        ct0 = os.environ.get("TWITTER_CT0") or child_env.get("TWITTER_CT0")
        if auth_token and ct0:
            return "ok", (
                "twitter-cli 已安装，且 Cookie-Editor 凭据已配置；"
                "Doctor 不会执行 `twitter status`，因为上游在验证失败时会"
                "自动读取浏览器 Cookie。请在你明确同意时手动验证。"
            )
        return "warn", (
            "twitter-cli 已安装但没有完整的显式凭据。请用 Cookie-Editor "
            "从 x.com 导出后运行：\n"
            "  by-reach configure twitter-cookies\n"
            "Doctor 不会自动读取浏览器 Cookie。"
        )
