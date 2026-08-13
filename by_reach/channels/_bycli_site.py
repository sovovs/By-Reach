# -*- coding: utf-8 -*-
"""Capability-based readiness helper for byCLI-backed channels."""

from by_reach.bycli import ByCliUnavailableError, probe_bycli_capabilities
from by_reach.utils.url import host_matches

from .base import Channel

_MAX_ERROR_MESSAGE = 400


class ByCliSiteChannel(Channel):
    """A channel whose read path is supplied by one declared byCLI command."""

    capability: str = ""
    domains: tuple[str, ...] = ()

    def can_handle(self, url: str) -> bool:
        return host_matches(url, *self.domains)

    def _check_bycli(self):
        self.active_backend = None
        try:
            capabilities = probe_bycli_capabilities()
        except ByCliUnavailableError as exc:
            return "off", _bounded_bycli_error(exc)
        if not capabilities.has_read(self.capability):
            return "off", (
                f"byCLI 未声明 {self.capability} 的 read 能力。"
                "请安装或升级：npm install -g @sovovs/bycli"
            )
        self.active_backend = "bycli"
        return "ok", f"byCLI 可用（{self.capability}）"

    def check(self, config=None):
        return self._check_bycli()


def _bounded_bycli_error(exc: BaseException) -> str:
    detail = str(exc).replace("\n", " ").strip()
    if len(detail) > _MAX_ERROR_MESSAGE:
        detail = detail[:_MAX_ERROR_MESSAGE] + "…"
    return f"byCLI 能力检查失败：{detail or '不可用'}"
