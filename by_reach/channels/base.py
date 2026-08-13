# -*- coding: utf-8 -*-
"""
Channel base class — platform availability checking.

Each channel represents a platform (YouTube, Twitter, GitHub, etc.)
and provides:
  - can_handle(url) → does this URL belong to this platform?
  - check(config) → is the upstream tool installed and configured?

After installation, agents call upstream tools directly.

Backend routing semantics:
  - `backends` serializes the channel's approved executor policy. It is the
    public source for doctor output and future runtime routing.
  - `_probe_backends` and `probe_backends` temporarily preserve legacy health
    checks until those probes are removed or migrated in Task 6. They must not
    be exposed as the approved executor policy.
  - check() must set `self.active_backend` to the backend that is actually
    serving the channel right now (None when nothing usable is found).
    shutil.which() alone is NOT proof of health — a stale venv shim passes
    which() but cannot execute (see by_reach.probe). Channels should
    really execute a lightweight command before claiming a backend active.
  - Users can force a backend with config key `<channel>_backend`
    (or env var `<CHANNEL>_BACKEND`); the ordered helpers apply it to their
    respective public-policy or transitional-probe candidate lists.
"""

from abc import ABC, abstractmethod
from typing import List, Mapping, Optional, Sequence, Tuple

from by_reach.executor_policy import POLICIES, ChannelPolicy


class Channel(ABC):
    """Base class for all channels."""

    name: str = ""                    # e.g. "youtube"
    policy_name: str = ""             # defaults to the channel name
    description: str = ""             # e.g. "YouTube 视频和字幕"
    tier: int = 0                     # 0=zero-config, 1=needs free key, 2=needs setup
    _probe_backends: Tuple[str, ...] = ()
    _probe_backend_aliases: Tuple[Tuple[str, str], ...] = ()

    #: Backend currently serving this channel; set by check(), None = unavailable.
    active_backend: Optional[str] = None

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        for reserved_name in ("backends", "policy"):
            if reserved_name in cls.__dict__:
                raise TypeError(
                    f"{cls.__name__} may not override policy-controlled "
                    f"attribute {reserved_name!r}"
                )

    @property
    def policy(self) -> ChannelPolicy:
        """Return this channel's approved executor policy."""
        policy_name = self.policy_name or self.name
        try:
            return POLICIES[policy_name]
        except KeyError as exc:
            raise KeyError(
                f"unknown executor policy for channel {policy_name!r}"
            ) from exc

    @property
    def backends(self) -> List[str]:
        """Serialize the approved executor policy for public callers."""
        return [executor.name for executor in self.policy.executors]

    @property
    def probe_backends(self) -> Tuple[str, ...]:
        """Legacy health-probe candidates pending Task 6 migration."""
        return self._probe_backends or tuple(self.backends)

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """Check if this channel can handle this URL."""
        ...

    def ordered_backends(self, config=None) -> List[str]:
        """Approved executors in policy order, honoring the user override.

        The config key `<channel>_backend` (env `<CHANNEL>_BACKEND`) moves the
        named executor to the front of the list. Unknown values are ignored.
        """
        return self._ordered_candidates(self.backends, config)

    def ordered_probe_backends(self, config=None) -> List[str]:
        """Legacy health probes in configured order pending Task 6."""
        return self._ordered_candidates(
            self.probe_backends,
            config,
            aliases=dict(self._probe_backend_aliases),
        )

    def _ordered_candidates(
        self,
        source: Sequence[str],
        config: Optional[Mapping[str, str]] = None,
        *,
        aliases: Optional[Mapping[str, str]] = None,
    ) -> List[str]:
        candidates = list(source)
        override = config.get(f"{self.name}_backend") if config else None
        if override:
            if aliases:
                override = aliases.get(override, override)
            for i, b in enumerate(candidates):
                if b == override:
                    candidates.insert(0, candidates.pop(i))
                    break
        return candidates

    def check(self, config=None) -> Tuple[str, str]:
        """
        Check if this channel's upstream tool is available.
        Returns (status, message) where status is 'ok'/'warn'/'off'/'error'.

        Subclasses with external backends must really probe them (see
        by_reach.probe.probe_command) and set self.active_backend.
        """
        probes = self.probe_backends
        self.active_backend = probes[0] if probes else "内置"
        return "ok", f"{'、'.join(probes) if probes else '内置'}"
