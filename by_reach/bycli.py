"""Safe byCLI capability discovery and generic webpage reading."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from by_reach.executor_runtime import (
    Attempt,
    ExecutionResult,
    execute_chain,
    run_command,
)
from by_reach.utils.url import Resolver, resolve_public_http_url

_CAPABILITY_TIMEOUT_SECONDS = 10
_WEB_READ_TIMEOUT_SECONDS = 30
_KNOWN_ACCESS_VALUES = frozenset({"read", "write"})

Runner = Callable[..., ExecutionResult]
_CAPABILITIES_FACTORY_TOKEN = object()


@dataclass(frozen=True)
class _CapabilityEntry:
    access: str
    fingerprint: str


class ByCliError(RuntimeError):
    """Base class for safe user-facing byCLI failures."""


class ByCliUnavailableError(ByCliError):
    """byCLI cannot currently provide a required capability."""


class ByCliManifestError(ByCliUnavailableError):
    """The byCLI capability manifest is invalid or ambiguous."""


class ByCliExecutionError(ByCliError):
    """A supported byCLI content command failed validation."""


class ByCliCapabilities:
    """A validated, immutable view of a byCLI command manifest.

    Current byCLI manifests declare ``read`` and ``write`` access. Only the
    exact ``read`` value grants read capability; write access is never promoted.
    Identical duplicate entries are deduplicated, while any conflicting duplicate
    fails closed.
    """

    def __init__(
        self,
        entries: Mapping[str, _CapabilityEntry] | None = None,
        *,
        _factory_token: object | None = None,
    ):
        if _factory_token is not _CAPABILITIES_FACTORY_TOKEN or entries is None:
            raise TypeError("use ByCliCapabilities.from_json()")
        self._entries = MappingProxyType(dict(entries))

    @classmethod
    def from_json(cls, payload: str) -> "ByCliCapabilities":
        if not isinstance(payload, str):
            raise TypeError("payload must be a JSON string")

        validation = execute_chain(
            [
                Attempt(
                    "byCLI capability manifest",
                    lambda: ExecutionResult(0, payload, ""),
                    output_format="json",
                    terminal=True,
                )
            ]
        )
        if validation.error is not None:
            raise ByCliManifestError(
                "byCLI capability manifest is not bounded strict JSON"
            )

        assert validation.output is not None
        try:
            parsed = json.loads(
                validation.output,
                parse_constant=_reject_nonstandard_json_constant,
            )
        except (json.JSONDecodeError, ValueError, TypeError, RecursionError) as exc:
            raise ByCliManifestError(
                "byCLI capability manifest is not bounded strict JSON"
            ) from exc

        if not isinstance(parsed, list):
            raise ByCliManifestError("byCLI capability manifest must be a list")

        entries: dict[str, _CapabilityEntry] = {}
        for index, raw_entry in enumerate(parsed):
            if not isinstance(raw_entry, dict):
                raise ByCliManifestError(
                    f"byCLI capability manifest entry {index} must be an object"
                )

            command = raw_entry.get("command")
            if not isinstance(command, str) or not command.strip():
                raise ByCliManifestError(
                    f"byCLI capability manifest entry {index} has an invalid command"
                )
            if command != command.strip():
                raise ByCliManifestError(
                    f"byCLI capability manifest entry {index} has an invalid command"
                )

            access = raw_entry.get("access")
            if not isinstance(access, str) or access not in _KNOWN_ACCESS_VALUES:
                raise ByCliManifestError(
                    f"byCLI capability manifest entry {index} has unknown access"
                )

            try:
                fingerprint = json.dumps(
                    raw_entry,
                    allow_nan=False,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
            except (TypeError, ValueError, RecursionError) as exc:
                raise ByCliManifestError(
                    f"byCLI capability manifest entry {index} is not valid JSON"
                ) from exc

            previous = entries.get(command)
            if previous is not None:
                if previous.fingerprint != fingerprint:
                    raise ByCliManifestError(
                        "byCLI capability manifest has conflicting duplicate "
                        f"at entry {index}"
                    )
                continue
            entries[command] = _CapabilityEntry(access, fingerprint)

        return cls(entries, _factory_token=_CAPABILITIES_FACTORY_TOKEN)

    def __len__(self) -> int:
        return len(self._entries)

    def has_read(self, command: str) -> bool:
        entry = self._entries.get(command)
        return entry is not None and entry.access == "read"

    @classmethod
    def probe(cls, runner: Runner | None = None) -> "ByCliCapabilities":
        """Discover capabilities with one exact shell-free manifest command."""

        selected_runner = run_command if runner is None else runner
        result = execute_chain(
            [
                Attempt(
                    "byCLI capability probe",
                    lambda: selected_runner(
                        ["bycli", "list", "-f", "json"],
                        timeout=_CAPABILITY_TIMEOUT_SECONDS,
                    ),
                    output_format="json",
                    terminal=True,
                )
            ]
        )
        if result.error is not None:
            raise ByCliUnavailableError(
                f"byCLI capability probe failed: {result.error.detail}"
            )

        assert result.output is not None
        return cls.from_json(result.output)


def probe_bycli_capabilities(*, runner: Runner | None = None) -> ByCliCapabilities:
    """Return a validated capability manifest from one exact shell-free probe."""

    return ByCliCapabilities.probe(runner)


def read_web(
    url: str,
    *,
    runner: Runner | None = None,
    resolver: Resolver | None = None,
) -> str:
    """Read Markdown after syntax checks and an initial DNS preflight.

    By-Reach validates the initial resolved addresses before any byCLI process
    runs. Redirect, subresource, and DNS connection-pinning enforcement belongs
    to byCLI's browser/network boundary because byCLI owns the navigation.
    """

    normalized_url = resolve_public_http_url(url, resolver=resolver)
    selected_runner = run_command if runner is None else runner
    capabilities = probe_bycli_capabilities(runner=selected_runner)
    if not capabilities.has_read("web/read"):
        raise ByCliUnavailableError(
            "byCLI does not advertise read capability for web/read"
        )

    result = execute_chain(
        [
            Attempt(
                "byCLI web/read",
                lambda: selected_runner(
                    [
                        "bycli",
                        "web",
                        "read",
                        "--url",
                        normalized_url,
                        "--stdout",
                    ],
                    timeout=_WEB_READ_TIMEOUT_SECONDS,
                ),
                output_format="text",
                terminal=True,
            )
        ]
    )
    if result.error is not None:
        raise ByCliExecutionError(f"byCLI web/read failed: {result.error.detail}")

    assert result.output is not None
    return result.output


def _reject_nonstandard_json_constant(constant: str) -> None:
    raise ValueError(f"non-standard JSON constant: {constant}")
