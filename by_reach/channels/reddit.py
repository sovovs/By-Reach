# -*- coding: utf-8 -*-
"""Reddit — explicit rdt-cli credentials, then byCLI. Login is mandatory.

Honest tiering (live-verified 2026-06): there is NO zero-config path.
Anonymous .json endpoints are blocked (403 anti-bot, all variants), and
the official API closed self-service registration in 2025-11 (manual
approval, individual scripts rarely granted — PRAW is only an option for
users who already hold credentials). Every working backend rides a
logged-in session: rdt-cli imports cookies or byCLI serves the declared read path.
"""

import json
import shutil
import time
from pathlib import Path

from by_reach.utils.paths import (
    PrivatePathError,
    read_small_text_no_follow,
)

from ._bycli_site import ByCliSiteChannel

_CREDENTIAL_FILE = "~/.config/rdt-cli/credential.json"
_CREDENTIAL_TTL_SECONDS = 7 * 86400
_MAX_CREDENTIAL_BYTES = 1024 * 1024
# Pinned to the 0.4.2 state — PyPI still only has 0.4.1 (upstream issue #10).
_RDT_GIT_SOURCE = "git+https://github.com/public-clis/rdt-cli.git@5e4fb3720d5c174e976cd425ccc3b879d52cac66"

class RedditChannel(ByCliSiteChannel):
    name = "reddit"
    description = "Reddit 帖子和评论"
    capability = "reddit/search"
    tier = 1  # no zero-config path exists — see module docstring

    def can_handle(self, url: str) -> bool:
        from by_reach.utils.url import host_matches

        return host_matches(url, "reddit.com", "redd.it")

    def check(self, config=None):
        self.active_backend = None
        primary = self._check_rdt()
        if primary is not None and primary[0] == "ok":
            self.active_backend = "rdt-cli"
            return primary
        fallback = self._check_bycli()
        if fallback[0] == "ok":
            self.active_backend = "bycli"
            return fallback
        self.active_backend = None
        return primary or fallback

    def _check_rdt(self):
        """Inspect rdt's saved credential without invoking its auto-refresh."""
        if not shutil.which("rdt"):
            return None

        credential_path = Path.home() / ".config" / "rdt-cli" / "credential.json"
        try:
            payload = read_small_text_no_follow(
                credential_path,
                max_bytes=_MAX_CREDENTIAL_BYTES,
            )
        except PrivatePathError as exc:
            return "warn", (
                f"rdt-cli 已安装，但 credential.json 无法安全读取：{exc}。"
            )
        except OSError:
            return "warn", (
                "rdt-cli 已安装，但 credential.json 无法安全读取；"
                "Doctor 未执行会自动刷新 Cookie 的 `rdt status`。"
            )
        if payload is None:
            return "warn", self._rdt_login_hint()
        try:
            data = json.loads(payload)
        except (UnicodeError, json.JSONDecodeError, ValueError):
            return "warn", (
                "rdt-cli 已安装，但保存的 credential.json 无法安全解析；"
                "Doctor 未执行会自动刷新 Cookie 的 `rdt status`。"
            )
        if not isinstance(data, dict):
            return "warn", self._rdt_login_hint()
        cookies = data.get("cookies")
        if not isinstance(cookies, dict) or not cookies.get("reddit_session"):
            return "warn", self._rdt_login_hint()

        saved_at = data.get("saved_at")
        if isinstance(saved_at, (int, float)) and (
            time.time() - saved_at > _CREDENTIAL_TTL_SECONDS
        ):
            return "warn", (
                "rdt-cli 已安装，保存的 Cookie 已超过 7 天；Doctor 不会让"
                "上游自动读取浏览器或刷新文件，请用 Cookie-Editor 明确更新。"
            )
        return "ok", (
            "rdt-cli 已安装并检测到显式保存的 Reddit Cookie；Doctor 为避免"
            "上游自动刷新浏览器 Cookie，不执行 `rdt status`，因此未实时验证。"
        )

    @staticmethod
    def _rdt_login_hint():
        return (
            "rdt-cli 已安装但没有可用的显式 Cookie。请使用 Cookie-Editor：\n"
            "  1. Chrome 应用商店安装 Cookie-Editor 扩展：\n"
            "     https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm\n"
            "  2. 在浏览器打开 reddit.com（确保已登录）\n"
            "  3. 点击 Cookie-Editor 图标，找到 `reddit_session`，复制其 Value\n"
            f"  4. 将以下内容写入 {_CREDENTIAL_FILE}：\n"
            '     {"cookies": {"reddit_session": "<粘贴 Value>"}, '
            '"source": "manual", "username": "<你的用户名>", '
            '"modhash": null, "saved_at": 0, "last_verified_at": null}\n\n'
            "Doctor 不会运行会自动读取浏览器并写文件的 `rdt status`。"
        )
