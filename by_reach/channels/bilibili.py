# -*- coding: utf-8 -*-
"""Bilibili — bili-cli first, then byCLI.

yt-dlp was REMOVED from this channel (live-verified 2026-06): bilibili's
risk control 412-blocks yt-dlp's requests in every configuration we
tried — latest version, direct, proxied, with warmed cookies — while
bili-cli keeps working (search/hot/video detail without login) and
yt-dlp remains the YouTube backend; it does not serve bilibili.
"""

from by_reach.probe import probe_command

from ._bycli_site import ByCliSiteChannel


class BilibiliChannel(ByCliSiteChannel):
    name = "bilibili"
    description = "B站视频、字幕和搜索"
    capability = "bilibili/search"
    tier = 1

    def can_handle(self, url: str) -> bool:
        from by_reach.utils.url import host_matches

        return host_matches(url, "bilibili.com", "b23.tv")

    def check(self, config=None):
        self.active_backend = None
        primary = self._check_bili_cli()
        if primary is not None and primary[0] == "ok":
            self.active_backend = "bili-cli"
            return primary
        fallback = self._check_bycli()
        if fallback[0] == "ok":
            self.active_backend = "bycli"
            return fallback
        self.active_backend = None
        return primary or fallback

    def _check_bili_cli(self):
        """bili-cli candidate. None = not installed."""
        probe = probe_command("bili", ["--version"], timeout=10, package="bilibili-cli")
        if probe.status == "missing":
            return None
        if probe.status == "broken":
            return "error", "bili 命令存在但无法执行\n" + probe.hint
        if not probe.ok:
            return "warn", f"bili-cli 探测失败（{probe.status}），运行 `bili status` 查看详情"
        return "ok", (
            "bili-cli 可用（搜索/热门/排行/视频详情/音频，无需登录；"
            "上游 2026-03 起停更）"
        )
