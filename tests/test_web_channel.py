"""The generic web channel is a terminal byCLI capability route."""

from __future__ import annotations

import json
import socket

import pytest

from by_reach.bycli import ByCliExecutionError, ByCliUnavailableError
from by_reach.channels.web import WebChannel
from by_reach.executor_runtime import MAX_CAPTURE_BYTES, TRUNCATION_MARKER, ExecutionResult


class RecordingRunner:
    def __init__(self, *results: ExecutionResult):
        self.results = iter(results)
        self.calls: list[tuple[list[str], float | None]] = []

    def __call__(self, args, timeout=None):
        self.calls.append((list(args), timeout))
        return next(self.results)


def _public_resolver(_host, port, **_kwargs):
    return [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            socket.IPPROTO_TCP,
            "",
            ("93.184.216.34", port),
        )
    ]


def _channel(runner):
    return WebChannel(runner=runner, resolver=_public_resolver)


def _manifest(access: str = "read") -> str:
    return json.dumps(
        [{"command": "web/read", "access": access, "site": "web"}]
    )


def _ready_runner(output: str = "# Example\nfull text\n") -> RecordingRunner:
    return RecordingRunner(
        ExecutionResult(0, _manifest(), ""),
        ExecutionResult(0, output, ""),
    )


def test_can_handle_remains_a_routing_catch_all():
    channel = _channel(RecordingRunner())

    for sample in [
        "https://example.com",
        "http://example.com/path?q=1",
        "example.com",
        "ftp://files.example.com/readme.txt",
        "not a url at all",
        "",
    ]:
        assert channel.can_handle(sample) is True, sample


def test_policy_and_probe_backends_are_only_bycli():
    channel = _channel(RecordingRunner())

    assert channel.backends == ["bycli"]
    assert channel.probe_backends == ("bycli",)


def test_check_is_ready_only_when_manifest_confirms_web_read():
    runner = RecordingRunner(ExecutionResult(0, _manifest(), ""))
    channel = _channel(runner)

    status, message = channel.check()

    assert status == "ok"
    assert channel.active_backend == "bycli"
    assert "web/read" in message
    assert runner.calls == [(["bycli", "list", "-f", "json"], 10)]


def test_check_missing_read_capability_is_honest_and_clears_active_backend():
    runner = RecordingRunner(ExecutionResult(0, _manifest("write"), ""))
    channel = _channel(runner)
    channel.active_backend = "bycli"

    status, message = channel.check()

    assert status == "off"
    assert channel.active_backend is None
    assert "read capability" in message


@pytest.mark.parametrize(
    "probe_result",
    [
        ExecutionResult(127, "", "not found"),
        ExecutionResult(0, "not-json", ""),
        ExecutionResult(0, "{}", ""),
    ],
)
def test_check_unavailable_or_invalid_probe_reports_error_and_clears_active(
    probe_result,
):
    runner = RecordingRunner(probe_result)
    channel = _channel(runner)
    channel.active_backend = "bycli"

    status, message = channel.check()

    assert status == "error"
    assert channel.active_backend is None
    assert "byCLI" in message


def test_read_delegates_only_to_bycli_and_preserves_markdown_exactly():
    runner = _ready_runner("café ☕\n")
    channel = _channel(runner)

    assert channel.read("http://example.com/deep") == "café ☕\n"
    assert runner.calls[-1] == (
        [
            "bycli",
            "web",
            "read",
            "--url",
            "http://example.com/deep",
            "--stdout",
        ],
        30,
    )


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/file",
        "http://localhost/admin",
        "http://intranet/admin",
        "http://home.arpa/admin",
        "http://metadata.google.internal/latest/meta-data",
        "http://127.0.0.1/private",
        "http://127.1/private",
        "http://169.254.169.254/latest/meta-data",
        "http://192.168.1/private",
        "http://0/private",
        "http://2130706433/private",
        "http://0x7f000001/private",
        "http://0177.0.0.1/private",
        "http://2852039166/latest/meta-data",
        "http://0xA9FEA9FE/latest/meta-data",
        "http://[::1]/private",
        "http://[::ffff:127.0.0.1]/private",
        "http://localhost./admin",
        "http://127.0.0.1\\example.com/private",
        "https://user:password@example.com/private",
    ],
)
def test_read_rejects_non_public_urls_before_probe_or_runner(url):
    runner = RecordingRunner()
    channel = _channel(runner)

    with pytest.raises(ValueError, match="public HTTP"):
        channel.read(url)

    assert runner.calls == []


@pytest.mark.parametrize(
    "url",
    [
        "http://metadata.google.internal。/latest/meta-data",
        "http://LOCALHOST．/admin",
        "http://foo｡internal｡/admin",
        "http://１２７。０。０。１/admin",
    ],
)
def test_read_rejects_unicode_separator_ssrf_before_probe_or_runner(url):
    runner = RecordingRunner()

    with pytest.raises(ValueError, match="public HTTP"):
        _channel(runner).read(url)

    assert runner.calls == []


@pytest.mark.parametrize(
    "url",
    ["https://8.8.8.8/page", "http://010.010.010.010/page"],
)
def test_read_allows_public_literal_addresses(url):
    runner = _ready_runner()

    _channel(runner).read(url)

    assert len(runner.calls) == 2


def test_probe_failure_is_terminal_and_never_calls_web_read():
    runner = RecordingRunner(ExecutionResult(1, "", "manifest unavailable"))

    with pytest.raises(ByCliUnavailableError, match="capability probe"):
        _channel(runner).read("https://example.com")

    assert len(runner.calls) == 1


def test_read_failure_is_terminal_with_useful_stderr():
    runner = RecordingRunner(
        ExecutionResult(0, _manifest(), ""),
        ExecutionResult(1, "", "browser unavailable"),
    )

    with pytest.raises(ByCliExecutionError, match="browser unavailable"):
        _channel(runner).read("https://example.com")

    assert len(runner.calls) == 2


@pytest.mark.parametrize(
    "body",
    [
        "",
        "   \n",
        (
            "<html><title>Attention Required! | Cloudflare</title>"
            '<script src="/cdn-cgi/challenge-platform/main.js"></script>'
            "<p>Cloudflare Ray ID: 123</p></html>"
        ),
        '<html><title>Access Denied</title><body>blocked</body></html>',
    ],
)
def test_read_inherits_terminal_empty_and_challenge_validation(body):
    runner = _ready_runner(body)

    with pytest.raises(ByCliExecutionError):
        _channel(runner).read("https://example.com")

    assert len(runner.calls) == 2


def test_read_inherits_bounded_text_output_semantics():
    runner = _ready_runner("x" * (MAX_CAPTURE_BYTES + 1))

    output = _channel(runner).read("https://example.com")

    assert len(output.encode("utf-8")) == MAX_CAPTURE_BYTES
    assert output.endswith(TRUNCATION_MARKER)


def test_read_dns_private_answer_is_rejected_before_runner():
    runner = RecordingRunner()

    def private_resolver(_host, port, **_kwargs):
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("10.0.0.1", port),
            )
        ]

    channel = WebChannel(runner=runner, resolver=private_resolver)

    with pytest.raises(ValueError, match="public HTTP"):
        channel.read("https://public.example")

    assert runner.calls == []
