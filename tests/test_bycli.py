"""Capability discovery and generic webpage execution through byCLI."""

from __future__ import annotations

import json

import pytest

from by_reach.bycli import (
    ByCliCapabilities,
    ByCliExecutionError,
    ByCliManifestError,
    ByCliUnavailableError,
    probe_bycli_capabilities,
    read_web,
)
from by_reach.executor_runtime import ExecutionResult


def _public_resolver(_host, port, **_kwargs):
    return [
        (
            2,
            1,
            6,
            "",
            ("93.184.216.34", port),
        )
    ]


class RecordingRunner:
    def __init__(self, *results: ExecutionResult):
        self.results = iter(results)
        self.calls: list[tuple[list[str], float | None]] = []

    def __call__(self, args, timeout=None):
        self.calls.append((list(args), timeout))
        return next(self.results)


def _manifest(*entries: object) -> str:
    return json.dumps(list(entries))


def _web_read_entry(**changes: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "command": "web/read",
        "access": "read",
        "site": "web",
    }
    entry.update(changes)
    return entry


def test_capabilities_accept_manifest_entries_and_expose_read_access():
    capabilities = ByCliCapabilities.from_json(_manifest(_web_read_entry()))

    assert capabilities.has_read("web/read") is True


def test_capabilities_accept_rich_real_manifest_metadata():
    entry = _web_read_entry(
        aliases=[],
        browser=True,
        args=[
            {
                "name": "url",
                "type": "str",
                "required": True,
                "default": None,
                "choices": [],
            }
        ],
        columns=["title", "content"],
        description="Read a webpage",
        strategy="browser",
    )

    capabilities = ByCliCapabilities.from_json(_manifest(entry))

    assert capabilities.has_read("web/read") is True


def test_capabilities_reject_direct_construction():
    with pytest.raises(TypeError, match="from_json"):
        ByCliCapabilities({})


def test_capabilities_do_not_retain_mutable_caller_manifest_objects():
    manifest = [_web_read_entry()]
    capabilities = ByCliCapabilities.from_json(json.dumps(manifest))

    manifest[0]["access"] = "write"

    assert capabilities.has_read("web/read") is True


def test_capabilities_from_json_rejects_non_string_overload():
    with pytest.raises(TypeError, match="JSON string"):
        ByCliCapabilities.from_json([_web_read_entry()])


def test_write_access_never_satisfies_read():
    capabilities = ByCliCapabilities.from_json(
        _manifest(_web_read_entry(access="write"))
    )

    assert capabilities.has_read("web/read") is False


@pytest.mark.parametrize(
    "payload",
    [
        "{}",
        '"not-a-list"',
        "[null]",
        '[{"access":"read"}]',
        '[{"command":7,"access":"read"}]',
        '[{"command":"","access":"read"}]',
        '[{"command":"   ","access":"read"}]',
        '[{"command":"web/read"}]',
        '[{"command":"web/read","access":7}]',
        '[{"command":"web/read","access":"admin"}]',
    ],
)
def test_manifest_parser_rejects_invalid_shapes_and_fields(payload):
    with pytest.raises(ByCliManifestError):
        ByCliCapabilities.from_json(payload)


def test_manifest_parser_rejects_json_beyond_runtime_nesting_limit():
    nested_metadata = "[" * 129 + "0" + "]" * 129
    payload = (
        '[{"command":"web/read","access":"read","site":"web",'
        f'"metadata":{nested_metadata}}}]'
    )

    with pytest.raises(ByCliManifestError, match="strict JSON"):
        ByCliCapabilities.from_json(payload)


def test_identical_duplicate_capabilities_are_deduplicated():
    entry = _web_read_entry()

    capabilities = ByCliCapabilities.from_json(_manifest(entry, entry))

    assert len(capabilities) == 1
    assert capabilities.has_read("web/read") is True


def test_duplicate_capabilities_with_reordered_object_keys_are_deduplicated():
    payload = (
        '[{"command":"web/read","access":"read","metadata":{"a":1,"b":2}},'
        '{"metadata":{"b":2,"a":1},"access":"read","command":"web/read"}]'
    )

    assert len(ByCliCapabilities.from_json(payload)) == 1


@pytest.mark.parametrize(
    ("first_value", "second_value"),
    [("true", "1"), ("false", "0"), ("1", "1.0")],
)
def test_duplicate_metadata_comparison_is_json_type_sensitive(
    first_value, second_value
):
    payload = (
        '[{"command":"web/read","access":"read","metadata":'
        f'{first_value}}},'
        '{"command":"web/read","access":"read","metadata":'
        f'{second_value}}}]'
    )

    with pytest.raises(ByCliManifestError, match="conflicting duplicate"):
        ByCliCapabilities.from_json(payload)


@pytest.mark.parametrize(
    "second",
    [
        _web_read_entry(access="write"),
        _web_read_entry(site="generic-web"),
    ],
)
def test_conflicting_duplicate_capabilities_are_rejected(second):
    with pytest.raises(ByCliManifestError, match="conflicting duplicate"):
        ByCliCapabilities.from_json(_manifest(_web_read_entry(), second))


def test_conflicting_duplicate_error_does_not_echo_hostile_command():
    hostile_command = "x" * 1_000_000
    payload = _manifest(
        {"command": hostile_command, "access": "read"},
        {"command": hostile_command, "access": "write"},
    )

    with pytest.raises(ByCliManifestError) as raised:
        ByCliCapabilities.from_json(payload)

    assert len(str(raised.value).encode("utf-8")) < 256
    assert hostile_command[:100] not in str(raised.value)


def test_probe_uses_list_json_command_instead_of_version():
    runner = RecordingRunner(ExecutionResult(0, _manifest(_web_read_entry()), ""))

    capabilities = probe_bycli_capabilities(runner=runner)

    assert capabilities.has_read("web/read")
    assert runner.calls == [(["bycli", "list", "-f", "json"], 10)]


def test_capabilities_classmethod_probe_makes_exactly_one_manifest_call():
    runner = RecordingRunner(ExecutionResult(0, _manifest(_web_read_entry()), ""))

    capabilities = ByCliCapabilities.probe(runner)

    assert capabilities.has_read("web/read")
    assert runner.calls == [(["bycli", "list", "-f", "json"], 10)]


@pytest.mark.parametrize(
    "result",
    [
        ExecutionResult(127, "", "bycli missing"),
        ExecutionResult(0, "not-json", ""),
        ExecutionResult(0, "", ""),
    ],
)
def test_failed_or_invalid_probe_is_typed_unavailable(result):
    runner = RecordingRunner(result)

    with pytest.raises(ByCliUnavailableError, match="capability probe"):
        probe_bycli_capabilities(runner=runner)


def test_valid_json_with_invalid_manifest_is_typed_manifest_error():
    runner = RecordingRunner(ExecutionResult(0, "{}", ""))

    with pytest.raises(ByCliManifestError, match="manifest"):
        probe_bycli_capabilities(runner=runner)


def test_read_web_probes_once_then_runs_exact_terminal_command():
    runner = RecordingRunner(
        ExecutionResult(0, _manifest(_web_read_entry()), ""),
        ExecutionResult(0, "# Example\nbody\n", ""),
    )

    output = read_web(
        "example.com/article", runner=runner, resolver=_public_resolver
    )

    assert output == "# Example\nbody\n"
    assert runner.calls == [
        (["bycli", "list", "-f", "json"], 10),
        (
            [
                "bycli",
                "web",
                "read",
                "--url",
                "https://example.com/article",
                "--stdout",
            ],
            30,
        ),
    ]


def test_read_web_missing_capability_is_terminal_before_content_command():
    runner = RecordingRunner(
        ExecutionResult(
            0,
            _manifest({"command": "web/read", "access": "write", "site": "web"}),
            "",
        )
    )

    with pytest.raises(ByCliUnavailableError, match="does not advertise read capability"):
        read_web(
            "https://example.com", runner=runner, resolver=_public_resolver
        )

    assert len(runner.calls) == 1


def test_read_web_command_failure_has_safe_useful_typed_error():
    runner = RecordingRunner(
        ExecutionResult(0, _manifest(_web_read_entry()), ""),
        ExecutionResult(
            1,
            "",
            "browser unavailable at https://user:pass@example.test/?token=secret",
        ),
    )

    with pytest.raises(ByCliExecutionError) as raised:
        read_web(
            "https://example.com", runner=runner, resolver=_public_resolver
        )

    message = str(raised.value)
    assert "browser unavailable" in message
    assert "user:pass" not in message
    assert "secret" not in message
    assert "***" in message


def test_read_web_failure_scrubs_oauth_client_secret_and_keeps_context():
    runner = RecordingRunner(
        ExecutionResult(0, _manifest(_web_read_entry()), ""),
        ExecutionResult(
            1,
            "",
            "browser unavailable at https://example.test/?client_secret=TOPSECRET",
        ),
    )

    with pytest.raises(ByCliExecutionError) as raised:
        read_web(
            "https://example.com", runner=runner, resolver=_public_resolver
        )

    message = str(raised.value)
    assert "browser unavailable" in message
    assert "TOPSECRET" not in message
    assert "client_secret=***" in message


@pytest.mark.parametrize(
    "resolver",
    [
        lambda *_args, **_kwargs: [],
        lambda *_args, **_kwargs: [
            (2, 1, 6, "", ("127.0.0.1", 443))
        ],
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("DNS failed")),
    ],
)
def test_read_web_dns_rejection_happens_before_capability_runner(resolver):
    runner = RecordingRunner()

    with pytest.raises(ValueError, match="public HTTP"):
        read_web("https://example.com", runner=runner, resolver=resolver)

    assert runner.calls == []
