# -*- coding: utf-8 -*-
"""Generic public webpages through byCLI's declared ``web/read`` capability."""

from __future__ import annotations

from by_reach.bycli import (
    ByCliManifestError,
    ByCliUnavailableError,
    Runner,
    probe_bycli_capabilities,
    read_web,
)
from by_reach.utils.url import Resolver

from .base import Channel


class WebChannel(Channel):
    name = "web"
    description = "任意网页"
    _probe_backends = ("bycli",)
    tier = 0

    def __init__(
        self,
        runner: Runner | None = None,
        resolver: Resolver | None = None,
    ):
        self._runner = runner
        self._resolver = resolver
        self.active_backend = None

    def can_handle(self, url: str) -> bool:
        return True

    def check(self, config=None):
        self.active_backend = None
        try:
            capabilities = probe_bycli_capabilities(runner=self._runner)
        except (ByCliManifestError, ByCliUnavailableError) as exc:
            return "error", str(exc)

        if not capabilities.has_read("web/read"):
            return "off", "byCLI does not advertise read capability for web/read"

        self.active_backend = "bycli"
        return "ok", "byCLI web/read capability is available"

    def read(self, url: str) -> str:
        return read_web(url, runner=self._runner, resolver=self._resolver)
