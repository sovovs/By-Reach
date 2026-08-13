"""Tests for shell-free executor invocation and ordered fallback semantics."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from types import SimpleNamespace

import pytest

from by_reach import executor_runtime
from by_reach.executor_runtime import (
    MAX_CAPTURE_BYTES,
    MAX_JSON_NESTING_DEPTH,
    MAX_SECRET_AGGREGATE_BYTES,
    MAX_SECRET_COUNT,
    MAX_SECRET_VALUE_BYTES,
    MIN_SECRET_LENGTH,
    TRUNCATION_MARKER,
    Attempt,
    ChainResult,
    ExecutionError,
    ExecutionResult,
    execute_chain,
    run_command,
)


def test_primary_success_stops_before_fallback():
    calls = []
    attempts = [
        Attempt(
            "twitter-cli",
            lambda: calls.append("twitter") or ExecutionResult(0, '[{"id":"1"}]', ""),
        ),
        Attempt(
            "bycli",
            lambda: calls.append("bycli") or ExecutionResult(0, "fallback", ""),
            terminal=True,
        ),
    ]

    result = execute_chain(attempts)

    assert result.output == '[{"id":"1"}]'
    assert result.error is None
    assert calls == ["twitter"]


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("_normalized", True),
        ("stdout_truncated", True),
        ("stdout_had_content", True),
        ("stdout_challenge_detected", False),
        ("stdout_json_valid", True),
    ],
)
def test_execution_result_constructor_rejects_validation_metadata(field_name, value):
    with pytest.raises(TypeError):
        ExecutionResult(0, "content", "", **{field_name: value})


def test_replace_normalized_result_with_whitespace_revalidates_and_falls_back():
    trusted = run_command([sys.executable, "-c", "print('content')"])
    replaced = replace(trusted, stdout="   ")

    result = execute_chain(
        [
            Attempt("primary", lambda: replaced),
            Attempt("bycli", lambda: ExecutionResult(0, "fallback", ""), terminal=True),
        ]
    )

    assert result.output == "fallback"


def test_replace_normalized_result_with_malformed_json_revalidates_and_falls_back():
    trusted = run_command([sys.executable, "-c", "print('{}')"])
    replaced = replace(trusted, stdout='{"unterminated":')

    result = execute_chain(
        [
            Attempt("primary", lambda: replaced, output_format="json"),
            Attempt("bycli", lambda: ExecutionResult(0, "fallback", ""), terminal=True),
        ]
    )

    assert result.output == "fallback"


def test_replace_normalized_result_with_challenge_page_revalidates_and_falls_back():
    trusted = run_command([sys.executable, "-c", "print('content')"])
    challenge = "<html><title>Access Denied</title><body>blocked</body></html>"
    replaced = replace(trusted, stdout=challenge)

    result = execute_chain(
        [
            Attempt("primary", lambda: replaced),
            Attempt("bycli", lambda: ExecutionResult(0, "fallback", ""), terminal=True),
        ]
    )

    assert result.output == "fallback"


def test_unchanged_normalized_result_remains_a_valid_success():
    trusted = run_command([sys.executable, "-c", "print('content', end='')"])

    result = execute_chain(
        [Attempt("primary", lambda: trusted)]
    )

    assert result.output == "content"


def test_empty_primary_falls_back_once_to_bycli():
    calls = []
    attempts = [
        Attempt(
            "twitter-cli",
            lambda: calls.append("twitter") or ExecutionResult(0, "", ""),
        ),
        Attempt(
            "bycli",
            lambda: calls.append("bycli") or ExecutionResult(0, "content", ""),
            terminal=True,
        ),
    ]

    result = execute_chain(attempts)

    assert result.output == "content"
    assert calls == ["twitter", "bycli"]


def test_valid_json_empty_result_does_not_fallback():
    calls = []
    attempts = [
        Attempt(
            "primary",
            lambda: calls.append("primary") or ExecutionResult(0, "[]", ""),
            output_format="json",
        ),
        Attempt(
            "bycli",
            lambda: calls.append("bycli") or ExecutionResult(0, "content", ""),
            terminal=True,
        ),
    ]

    result = execute_chain(attempts)

    assert result.output == "[]"
    assert calls == ["primary"]


def test_terminal_failure_exposes_no_further_fallback():
    result = execute_chain(
        [Attempt("bycli", lambda: ExecutionResult(1, "", "failed"), terminal=True)]
    )

    assert result.output is None
    assert result.error is not None
    assert result.error.code == "executor_failed"
    assert result.error.attempted_executors == ("bycli",)
    assert result.error.fallback_allowed is False


def test_run_command_uses_argument_vector_shell_false_and_copied_env(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=7, stdout="output", stderr="warning")

    monkeypatch.setattr(executor_runtime.subprocess, "run", fake_run)
    args = ["tool", "value with spaces", "$(not-a-shell)"]
    env = {"PATH": "/safe/bin", "TOKEN": "value"}

    result = run_command(args, timeout=4.5, env=env)

    assert result == ExecutionResult(7, "output", "warning")
    assert result.output == "output"
    called_args, called_kwargs = calls[0]
    assert called_args == args
    assert called_args is not args
    assert called_kwargs == {
        "check": False,
        "capture_output": True,
        "encoding": "utf-8",
        "errors": "replace",
        "text": True,
        "timeout": 4.5,
        "env": env,
        "shell": False,
    }
    assert called_kwargs["env"] is not env


def test_run_command_decodes_invalid_process_bytes_with_replacement():
    result = run_command(
        [sys.executable, "-c", "import os; os.write(1, b'\\xff')"]
    )

    assert result.exit_code == 0
    assert result.stdout == "\ufffd"
    assert result.stdout.encode("utf-8") == b"\xef\xbf\xbd"


@pytest.mark.parametrize(
    "args",
    [
        [],
        "tool --flag",
        [""],
        ["tool", ""],
        ["tool", "bad\0argument"],
        ["tool", 3],
    ],
)
def test_run_command_rejects_invalid_arguments_before_subprocess(monkeypatch, args):
    def unexpected_run(*_args, **_kwargs):
        raise AssertionError("subprocess.run must not be called")

    monkeypatch.setattr(executor_runtime.subprocess, "run", unexpected_run)

    with pytest.raises((TypeError, ValueError)):
        run_command(args)


def test_run_command_bounds_each_stream_with_visible_marker(monkeypatch):
    monkeypatch.setattr(
        executor_runtime.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout="a" * (MAX_CAPTURE_BYTES + 1),
            stderr="b" * (MAX_CAPTURE_BYTES + 19),
        ),
    )

    result = run_command(["tool"])

    assert len(result.stdout.encode("utf-8")) == MAX_CAPTURE_BYTES
    assert len(result.stderr.encode("utf-8")) == MAX_CAPTURE_BYTES
    assert result.stdout.endswith(TRUNCATION_MARKER)
    assert result.stderr.endswith(TRUNCATION_MARKER)
    assert result.stdout.startswith("a" * 100)
    assert result.stderr.startswith("b" * 100)


@pytest.mark.parametrize(
    "size",
    [
        MAX_CAPTURE_BYTES,
        MAX_CAPTURE_BYTES - len(TRUNCATION_MARKER.encode("utf-8")) + 1,
    ],
)
def test_run_command_does_not_mark_output_within_exact_byte_limit(monkeypatch, size):
    output = "a" * size
    monkeypatch.setattr(
        executor_runtime.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout=output,
            stderr="",
        ),
    )

    result = run_command(["tool"])

    assert result.stdout == output
    assert len(result.stdout.encode("utf-8")) == size
    assert not result.stdout.endswith(TRUNCATION_MARKER)


def test_run_command_marks_output_only_when_strictly_over_byte_limit(monkeypatch):
    monkeypatch.setattr(
        executor_runtime.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout="a" * (MAX_CAPTURE_BYTES + 1),
            stderr="",
        ),
    )

    result = run_command(["tool"])

    assert len(result.stdout.encode("utf-8")) == MAX_CAPTURE_BYTES
    assert result.stdout.endswith(TRUNCATION_MARKER)


def test_run_command_bounds_multibyte_text_in_bytes(monkeypatch):
    monkeypatch.setattr(
        executor_runtime.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout="鲸" * MAX_CAPTURE_BYTES,
            stderr="",
        ),
    )

    result = run_command(["tool"])

    assert len(result.stdout.encode("utf-8")) <= MAX_CAPTURE_BYTES
    assert result.stdout.endswith(TRUNCATION_MARKER)


def test_run_command_redacts_url_credentials_and_configured_secrets(monkeypatch):
    explicit_secret = "super-secret-token"
    raw = (
        "http://user:pass@proxy.test/path?access_token=url-token "
        f"Authorization: {explicit_secret}; value: abcd; overlap: abcd123"
    )
    monkeypatch.setattr(
        executor_runtime.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout=raw, stderr=raw),
    )

    result = run_command(
        ["tool"], secret_values=[explicit_secret, "", "abcd", "abcd123"]
    )

    for stream in (result.stdout, result.stderr):
        assert "user:pass" not in stream
        assert "url-token" not in stream
        assert explicit_secret not in stream
        assert "abcd" not in stream
        assert "***123" not in stream  # Overlaps are redacted once, longest-first.
        assert "***" in stream


def test_url_query_values_are_scrubbed_before_secret_key_names(monkeypatch):
    raw = (
        "https://api.test/data?token=raw-token-value"
        "&access_token=raw-access-value&password=raw-password-value"
    )
    monkeypatch.setattr(
        executor_runtime.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout=raw, stderr=raw),
    )

    result = run_command(
        ["tool"], secret_values=["token", "access_token", "password"]
    )

    for stream in (result.stdout, result.stderr):
        assert "raw-token-value" not in stream
        assert "raw-access-value" not in stream
        assert "raw-password-value" not in stream
        assert "***" in stream


def test_url_query_values_stay_scrubbed_in_nonzero_chain_detail():
    raw = "https://api.test/data?token=raw-token-value&password=raw-password-value"
    result = execute_chain(
        [Attempt("bycli", lambda: ExecutionResult(1, "", raw), terminal=True)],
        secret_values=["token", "password"],
    )

    assert result.error is not None
    assert "raw-token-value" not in result.error.detail
    assert "raw-password-value" not in result.error.detail
    assert "***" in result.error.detail


def test_secret_trie_is_compiled_once_and_reused_for_both_streams(monkeypatch):
    compile_calls = []
    original_compile = executor_runtime._compile_secret_redactor

    def compile_once(secrets):
        compile_calls.append(secrets)
        return original_compile(secrets)

    monkeypatch.setattr(executor_runtime, "_compile_secret_redactor", compile_once)
    monkeypatch.setattr(
        executor_runtime.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=1,
            stdout="long-secret and small",
            stderr="long-secret and small",
        ),
    )

    result = run_command(["tool"], secret_values=["small", "long-secret"])

    assert compile_calls == [("long-secret", "small")]
    assert result.stdout == "*** and ***"
    assert result.stderr == "*** and ***"


@pytest.mark.parametrize(
    ("secrets", "output"),
    [
        (
            ["s" * MAX_SECRET_VALUE_BYTES]
            * (MAX_SECRET_AGGREGATE_BYTES // MAX_SECRET_VALUE_BYTES),
            "s" * MAX_SECRET_VALUE_BYTES,
        ),
        (["same"] * MAX_SECRET_COUNT, "same"),
    ],
)
def test_secret_limits_accept_boundaries_before_executing(
    monkeypatch, secrets, output
):
    calls = []
    monkeypatch.setattr(
        executor_runtime.subprocess,
        "run",
        lambda *_args, **_kwargs: calls.append("run")
        or SimpleNamespace(returncode=0, stdout=output, stderr=""),
    )

    result = run_command(["tool"], secret_values=secrets)

    assert calls == ["run"]
    assert result.stdout == "***"


@pytest.mark.parametrize(
    "secrets",
    [
        ["s" * (MAX_SECRET_VALUE_BYTES + 1)],
        [f"secret-{index}" for index in range(MAX_SECRET_COUNT + 1)],
        ["s" * MAX_SECRET_VALUE_BYTES]
        * (MAX_SECRET_AGGREGATE_BYTES // MAX_SECRET_VALUE_BYTES)
        + ["x"],
    ],
)
def test_secret_limits_reject_before_subprocess(monkeypatch, secrets):
    def unexpected_run(*_args, **_kwargs):
        raise AssertionError("subprocess.run must not execute")

    monkeypatch.setattr(executor_runtime.subprocess, "run", unexpected_run)

    with pytest.raises(ValueError, match="secret"):
        run_command(["tool"], secret_values=secrets)


def test_secret_limits_reject_before_executor_callable():
    calls = []
    attempts = [
        Attempt(
            "primary",
            lambda: calls.append("primary") or ExecutionResult(0, "content", ""),
        )
    ]

    with pytest.raises(ValueError, match="secret"):
        execute_chain(
            attempts,
            secret_values=["s" * (MAX_SECRET_VALUE_BYTES + 1)],
        )

    assert calls == []


@pytest.mark.parametrize(
    "secret",
    [
        "*",
        "***",
        "x" * (MIN_SECRET_LENGTH - 1),
        "trun",
        "***x",
        f"prefix{TRUNCATION_MARKER}suffix",
    ],
)
def test_unsupported_short_or_marker_colliding_secret_rejected_before_execution(
    monkeypatch, secret
):
    def unexpected_run(*_args, **_kwargs):
        raise AssertionError("subprocess.run must not execute")

    monkeypatch.setattr(executor_runtime.subprocess, "run", unexpected_run)

    with pytest.raises(ValueError, match="secret"):
        run_command(["tool"], secret_values=[secret])


@pytest.mark.parametrize(
    "secret",
    [
        "aa**",
        "**aa",
        "aa\n.",
        "]abc",
    ],
)
def test_marker_boundary_overlap_secret_rejected_before_child(monkeypatch, secret):
    def unexpected_run(*_args, **_kwargs):
        raise AssertionError("subprocess.run must not execute")

    monkeypatch.setattr(executor_runtime.subprocess, "run", unexpected_run)

    with pytest.raises(ValueError, match="secret"):
        run_command(["tool"], secret_values=[secret])


def test_marker_boundary_overlap_secret_rejected_before_callable():
    calls = []
    with pytest.raises(ValueError, match="secret"):
        execute_chain(
            [
                Attempt(
                    "primary",
                    lambda: calls.append("primary") or ExecutionResult(0, "ok", ""),
                )
            ],
            secret_values=["aa**"],
        )

    assert calls == []


@pytest.mark.parametrize("secret", ["aa*?", "?*aa", "normal-secret"])
def test_marker_boundary_near_miss_secret_is_accepted(monkeypatch, secret):
    calls = []
    monkeypatch.setattr(
        executor_runtime.subprocess,
        "run",
        lambda *_args, **_kwargs: calls.append("run")
        or SimpleNamespace(returncode=0, stdout=secret, stderr=""),
    )

    result = run_command(["tool"], secret_values=[secret])

    assert calls == ["run"]
    assert result.stdout == "***"


def test_common_prefix_secrets_use_non_regex_matcher(monkeypatch):
    def unexpected_compile(*_args, **_kwargs):
        raise AssertionError("secret matching must not compile regex alternation")

    monkeypatch.setattr(executor_runtime.re, "compile", unexpected_compile)
    secrets = ["a" * 64 + chr(0x100 + index) for index in range(MAX_SECRET_COUNT)]

    redactor = executor_runtime._prepare_secret_redactor(secrets)
    text = ("a" * 64 + "not-a-secret") * 4096 + secrets[-1]

    assert redactor.redact(text).endswith("***")
    assert secrets[-1] not in redactor.redact(text)


def test_run_command_scrubs_credentials_and_secret_crossing_capture_cut(monkeypatch):
    head_bytes = MAX_CAPTURE_BYTES - len(TRUNCATION_MARKER.encode("utf-8"))
    credential = "http://alice:supersecret@example.com/path"
    credential_prefix = "http://alice:super"
    stdout = (
        f"{'x' * (head_bytes - len(credential_prefix) - 1)} "
        f"{credential}-enough-trailing-data-to-remain-oversized"
    )
    explicit_secret = "crossboundary"
    secret_prefix = "cross"
    stderr = (
        f"{'y' * (head_bytes - len(secret_prefix) - 1)} "
        f"{explicit_secret}{'-trailing-data' * 4}"
    )
    monkeypatch.setattr(
        executor_runtime.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=1,
            stdout=stdout,
            stderr=stderr,
        ),
    )

    result = run_command(["tool"], secret_values=[explicit_secret])

    assert len(result.stdout.encode("utf-8")) <= MAX_CAPTURE_BYTES
    assert len(result.stderr.encode("utf-8")) <= MAX_CAPTURE_BYTES
    assert result.stdout.endswith(TRUNCATION_MARKER)
    assert result.stderr.endswith(TRUNCATION_MARKER)
    assert "alice" not in result.stdout
    assert "super" not in result.stdout
    assert "alice:supersecret" not in result.stdout
    assert "@example.com" not in result.stdout
    assert secret_prefix not in result.stderr
    assert explicit_secret not in result.stderr


def test_timeout_is_a_safe_nonzero_result_with_scrubbed_streams(monkeypatch):
    def time_out(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(
            cmd=["tool"],
            timeout=2,
            output="partial secret-value",
            stderr="http://user:pass@proxy.test failed secret-value",
        )

    monkeypatch.setattr(executor_runtime.subprocess, "run", time_out)

    result = run_command(["tool"], timeout=2, secret_values=["secret-value"])

    assert result.exit_code != 0
    assert "secret-value" not in result.stdout
    assert "secret-value" not in result.stderr
    assert "user:pass" not in result.stderr
    assert "timed out" in result.stderr.lower()


def test_timeout_query_values_are_scrubbed_before_secret_key_names(monkeypatch):
    raw = "https://api.test/data?token=raw-token-value&password=raw-password-value"

    def time_out(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(
            cmd=["tool"], timeout=2, output=raw, stderr=raw
        )

    monkeypatch.setattr(executor_runtime.subprocess, "run", time_out)

    result = run_command(["tool"], secret_values=["token", "password"])

    for stream in (result.stdout, result.stderr):
        assert "raw-token-value" not in stream
        assert "raw-password-value" not in stream


def test_missing_executable_is_a_safe_nonzero_result(monkeypatch):
    def missing(*_args, **_kwargs):
        raise FileNotFoundError("missing http://user:pass@proxy.test secret-value")

    monkeypatch.setattr(executor_runtime.subprocess, "run", missing)

    result = run_command(["missing"], secret_values=["secret-value"])

    assert result.exit_code != 0
    assert result.stdout == ""
    assert "user:pass" not in result.stderr
    assert "secret-value" not in result.stderr
    assert "***" in result.stderr


def test_os_error_query_values_are_scrubbed_before_secret_key_names(monkeypatch):
    raw = "https://api.test/data?token=raw-token-value&password=raw-password-value"

    def fail_to_start(*_args, **_kwargs):
        raise OSError(raw)

    monkeypatch.setattr(executor_runtime.subprocess, "run", fail_to_start)

    result = run_command(["tool"], secret_values=["token", "password"])

    assert result.exit_code != 0
    assert "raw-token-value" not in result.stderr
    assert "raw-password-value" not in result.stderr


def test_hostile_os_error_string_returns_safe_nonzero_result(monkeypatch):
    class HostileOSError(OSError):
        def __str__(self):
            raise RuntimeError("secret-value from __str__")

    def fail_to_start(*_args, **_kwargs):
        raise HostileOSError()

    monkeypatch.setattr(executor_runtime.subprocess, "run", fail_to_start)

    result = run_command(["tool"], secret_values=["secret-value"])

    assert result.exit_code != 0
    assert result.stdout == ""
    assert "secret-value" not in result.stderr
    assert "unavailable" in result.stderr


def test_lone_surrogates_are_normalized_in_results_names_and_errors():
    result = execute_chain(
        [
            Attempt(
                "executor-\ud800",
                lambda: ExecutionResult(
                    1,
                    "stdout-\ud800",
                    "stderr-\ud800 http://user:pass@proxy.test",
                ),
                terminal=True,
            )
        ]
    )

    assert result.error is not None
    result.error.detail.encode("utf-8")
    result.error.attempted_executors[0].encode("utf-8")
    assert "\ud800" not in repr(result.error)
    assert "user:pass" not in result.error.detail


def test_deep_json_falls_back_without_recursion_error():
    too_deep = "[" * (MAX_JSON_NESTING_DEPTH + 1) + "0" + "]" * (
        MAX_JSON_NESTING_DEPTH + 1
    )
    result = execute_chain(
        [
            Attempt(
                "primary",
                lambda: ExecutionResult(0, too_deep, ""),
                output_format="json",
            ),
            Attempt("bycli", lambda: ExecutionResult(0, "fallback", ""), terminal=True),
        ]
    )

    assert result.output == "fallback"


@pytest.mark.parametrize(
    "payload",
    [
        "[" * MAX_JSON_NESTING_DEPTH + "0" + "]" * MAX_JSON_NESTING_DEPTH,
        '"brackets in a string: [[[[{{{{ and escaped quote \\" ]"',
    ],
)
def test_json_depth_limit_ignores_brackets_in_strings_and_accepts_boundary(payload):
    result = execute_chain(
        [Attempt("primary", lambda: ExecutionResult(0, payload, ""), output_format="json")]
    )

    assert result.output == payload


def test_json_parser_recursion_error_becomes_fallback(monkeypatch):
    monkeypatch.setattr(
        executor_runtime.json,
        "loads",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RecursionError()),
    )

    result = execute_chain(
        [
            Attempt(
                "primary",
                lambda: ExecutionResult(0, "{}", ""),
                output_format="json",
            ),
            Attempt("bycli", lambda: ExecutionResult(0, "fallback", ""), terminal=True),
        ]
    )

    assert result.output == "fallback"


@pytest.mark.parametrize("payload", ["not json", "   "])
def test_malformed_or_blank_json_falls_back(payload):
    calls = []
    result = execute_chain(
        [
            Attempt(
                "primary",
                lambda: calls.append("primary") or ExecutionResult(0, payload, ""),
                output_format="json",
            ),
            Attempt(
                "bycli",
                lambda: calls.append("bycli") or ExecutionResult(0, "fallback", ""),
                terminal=True,
            ),
        ]
    )

    assert result.output == "fallback"
    assert calls == ["primary", "bycli"]


@pytest.mark.parametrize(
    "payload",
    ["NaN", "Infinity", "-Infinity", '[1, {"nested": NaN}]'],
)
def test_nonstandard_json_constants_fall_back(payload):
    calls = []
    result = execute_chain(
        [
            Attempt(
                "primary",
                lambda: calls.append("primary") or ExecutionResult(0, payload, ""),
                output_format="json",
            ),
            Attempt(
                "bycli",
                lambda: calls.append("bycli") or ExecutionResult(0, "fallback", ""),
                terminal=True,
            ),
        ]
    )

    assert result.output == "fallback"
    assert calls == ["primary", "bycli"]


@pytest.mark.parametrize("payload", ["null", "42", '"content"', "[]", "{}"])
def test_standard_json_scalars_and_empty_values_are_successful(payload):
    result = execute_chain(
        [Attempt("primary", lambda: ExecutionResult(0, payload, ""), output_format="json")]
    )

    assert result.output == payload
    assert result.error is None


def test_full_whitespace_output_stays_invalid_after_public_truncation():
    calls = []
    whitespace = " " * (MAX_CAPTURE_BYTES + 100)
    result = execute_chain(
        [
            Attempt(
                "primary",
                lambda: calls.append("primary") or ExecutionResult(0, whitespace, ""),
            ),
            Attempt(
                "bycli",
                lambda: calls.append("bycli") or ExecutionResult(0, "fallback", ""),
                terminal=True,
            ),
        ]
    )

    assert result.output == "fallback"
    assert calls == ["primary", "bycli"]


def test_challenge_beyond_public_output_cut_is_detected():
    calls = []
    challenge_page = (
        "x" * (MAX_CAPTURE_BYTES + 10)
        + "<html><title>Attention Required! | Cloudflare</title>"
        + '<script src="/cdn-cgi/challenge-platform/main.js"></script>'
        + "<p>Cloudflare Ray ID: 123</p></html>"
    )
    result = execute_chain(
        [
            Attempt(
                "primary",
                lambda: calls.append("primary")
                or ExecutionResult(0, challenge_page, ""),
            ),
            Attempt(
                "bycli",
                lambda: calls.append("bycli") or ExecutionResult(0, "fallback", ""),
                terminal=True,
            ),
        ]
    )

    assert result.output == "fallback"
    assert calls == ["primary", "bycli"]


def test_complete_valid_json_beyond_cut_falls_back_because_public_json_is_truncated():
    calls = []
    payload = '"' + ("a" * (MAX_CAPTURE_BYTES + 50)) + '"'
    result = execute_chain(
        [
            Attempt(
                "primary",
                lambda: calls.append("primary") or ExecutionResult(0, payload, ""),
                output_format="json",
            ),
            Attempt(
                "bycli",
                lambda: calls.append("bycli") or ExecutionResult(0, "fallback", ""),
                terminal=True,
            ),
        ]
    )

    assert result.output == "fallback"
    assert calls == ["primary", "bycli"]


def test_chain_secret_revalidates_json_from_already_normalized_result():
    normalized = run_command(
        [sys.executable, "-c", "print('\\\"foo\\\"', end='')"]
    )

    result = execute_chain(
        [
            Attempt("primary", lambda: normalized, output_format="json"),
            Attempt("bycli", lambda: ExecutionResult(0, "fallback", ""), terminal=True),
        ],
        secret_values=['foo"'],
    )

    assert result.output == "fallback"


def test_successful_declared_json_output_is_always_parseable():
    normalized = run_command(
        [sys.executable, "-c", "print('\\\"food\\\"', end='')"]
    )

    result = execute_chain(
        [Attempt("primary", lambda: normalized, output_format="json")],
        secret_values=["food"],
    )

    assert result.output is not None
    assert json.loads(result.output) == "***"


def test_complete_invalid_json_beyond_cut_falls_back():
    calls = []
    payload = '"' + ("a" * (MAX_CAPTURE_BYTES + 50))
    result = execute_chain(
        [
            Attempt(
                "primary",
                lambda: calls.append("primary") or ExecutionResult(0, payload, ""),
                output_format="json",
            ),
            Attempt(
                "bycli",
                lambda: calls.append("bycli") or ExecutionResult(0, "fallback", ""),
                terminal=True,
            ),
        ]
    )

    assert result.output == "fallback"
    assert calls == ["primary", "bycli"]


def test_nonzero_exit_falls_back_even_when_stdout_is_nonempty():
    result = execute_chain(
        [
            Attempt("primary", lambda: ExecutionResult(2, "stale content", "failed")),
            Attempt("bycli", lambda: ExecutionResult(0, "fallback", ""), terminal=True),
        ]
    )

    assert result.output == "fallback"


@pytest.mark.parametrize(
    ("payload", "output_format"),
    [
        (
            '<html><title>Attention Required! | Cloudflare</title><script src="/cdn-cgi/challenge-platform/scripts/jsd/main.js"></script></html>',
            "text",
        ),
        ("Just a moment... Enable JavaScript and cookies to continue", "text"),
        ('{"message": "CAPTCHA challenge: verify you are human"}', "json"),
        (
            '<html><body><h1>Captcha challenge</h1><iframe src="/recaptcha"></iframe></body></html>',
            "text",
        ),
        ("<html><title>Access Denied</title><body>blocked</body></html>", "text"),
        (
            '{"html": "<html><title>Error</title><body><div class=\\"error-wrapper\\">Access denied</div></body></html>"}',
            "json",
        ),
        ('{"error_wrapper":{"code":"blocked"}}', "json"),
        ('{"error_wrapper":true}', "json"),
    ],
)
def test_challenge_and_error_wrapper_outputs_fall_back(payload, output_format):
    calls = []
    result = execute_chain(
        [
            Attempt(
                "primary",
                lambda: calls.append("primary") or ExecutionResult(0, payload, ""),
                output_format=output_format,
            ),
            Attempt(
                "bycli",
                lambda: calls.append("bycli") or ExecutionResult(0, "fallback", ""),
                terminal=True,
            ),
        ]
    )

    assert result.output == "fallback"
    assert calls == ["primary", "bycli"]


@pytest.mark.parametrize(
    ("payload", "output_format"),
    [
        ("The parser reports an error when ordinary input is invalid.", "text"),
        (
            "This article discusses CAPTCHA accessibility and access denied behavior.",
            "text",
        ),
        (
            '{"article":"Researchers discuss CAPTCHA accessibility, access denied behavior, and error-wrapper CSS."}',
            "json",
        ),
        ('{"message":"CAPTCHA required for this integration test discussion"}', "json"),
        (
            "This article compares a CAPTCHA challenge with other accessibility patterns.",
            "text",
        ),
        ('Use class="error-wrapper" in documentation examples.', "text"),
        (
            '{"documentation":"Use class=\\"error-wrapper\\" for validation examples."}',
            "json",
        ),
        ("An article explains what a Cloudflare Ray ID means.", "text"),
        ('const widget = "cf-chl-widget";', "text"),
        ('{"error_wrapper":false}', "json"),
        ('{"captcha_challenge":"CSS class name"}', "json"),
    ],
)
def test_ordinary_challenge_words_are_not_false_positives(payload, output_format):

    result = execute_chain(
        [
            Attempt(
                "primary",
                lambda: ExecutionResult(0, payload, ""),
                output_format=output_format,
            )
        ]
    )

    assert result.output == payload


def test_callable_exception_is_scrubbed_and_can_fall_back():
    calls = []

    def fail():
        calls.append("primary")
        raise RuntimeError(
            "request via http://user:pass@proxy.test failed with secret-value"
        )

    result = execute_chain(
        [
            Attempt("primary", fail),
            Attempt(
                "bycli",
                lambda: calls.append("bycli") or ExecutionResult(0, "fallback", ""),
                terminal=True,
            ),
        ],
        secret_values=["secret-value"],
    )

    assert result.output == "fallback"
    assert calls == ["primary", "bycli"]


def test_terminal_callable_exception_returns_safe_error():
    def fail():
        raise RuntimeError(
            "request via http://user:pass@proxy.test failed with secret-value"
        )

    result = execute_chain(
        [Attempt("bycli", fail, terminal=True)], secret_values=["secret-value"]
    )

    assert result.error is not None
    assert "user:pass" not in result.error.detail
    assert "secret-value" not in result.error.detail
    assert "***" in result.error.detail
    assert result.error.fallback_allowed is False


def test_terminal_nonzero_result_includes_safe_stderr_excerpt():
    result = execute_chain(
        [
            Attempt(
                "bycli",
                lambda: ExecutionResult(
                    1,
                    "",
                    "browser unavailable via http://user:pass@proxy.test secret-value",
                ),
                terminal=True,
            )
        ],
        secret_values=["secret-value"],
    )

    assert result.error is not None
    assert "browser unavailable" in result.error.detail
    assert "user:pass" not in result.error.detail
    assert "secret-value" not in result.error.detail
    assert len(result.error.detail.encode("utf-8")) <= 4096


def test_hostile_exception_string_cannot_prevent_fallback():
    calls = []

    class HostileError(Exception):
        def __str__(self):
            raise RuntimeError("secret-value from __str__")

    def fail():
        calls.append("primary")
        raise HostileError()

    result = execute_chain(
        [
            Attempt("primary", fail),
            Attempt(
                "bycli",
                lambda: calls.append("bycli") or ExecutionResult(0, "fallback", ""),
                terminal=True,
            ),
        ],
        secret_values=["secret-value"],
    )

    assert result.output == "fallback"
    assert calls == ["primary", "bycli"]


def test_exception_type_name_message_and_composed_detail_are_sanitized():
    secret = "secret-value"
    secret_error_type = type(f"Failure_{secret}", (Exception,), {})

    def fail():
        raise secret_error_type(
            f"via http://alice:password@proxy.test/{secret} " + ("z" * 6000)
        )

    result = execute_chain(
        [Attempt("bycli", fail, terminal=True)], secret_values=[secret]
    )

    assert result.error is not None
    rendered_error = repr(result.error)
    assert secret not in rendered_error
    assert "alice" not in rendered_error
    assert "password" not in rendered_error
    assert len(result.error.detail.encode("utf-8")) <= 4096
    assert result.error.detail.endswith(TRUNCATION_MARKER)


def test_failure_redacts_executor_names_in_error_object():
    result = execute_chain(
        [
            Attempt(
                "bycli-secret-value-http://user:pass@proxy.test",
                lambda: ExecutionResult(1, "", "failed"),
                terminal=True,
            )
        ],
        secret_values=["secret-value"],
    )

    assert result.error is not None
    rendered_error = repr(result.error)
    assert "secret-value" not in rendered_error
    assert "user:pass" not in rendered_error
    assert "***" in rendered_error


def test_terminal_attempt_before_final_is_rejected_without_execution():
    calls = []
    attempts = [
        Attempt(
            "terminal",
            lambda: calls.append("terminal") or ExecutionResult(0, "content", ""),
            terminal=True,
        ),
        Attempt(
            "later",
            lambda: calls.append("later") or ExecutionResult(0, "later", ""),
        ),
    ]

    with pytest.raises(ValueError, match="terminal"):
        execute_chain(attempts)

    assert calls == []


def test_empty_and_duplicate_executor_chains_are_rejected_before_execution():
    with pytest.raises(ValueError, match="at least one"):
        execute_chain([])

    calls = []
    duplicate = [
        Attempt("same", lambda: calls.append("first") or ExecutionResult(1, "", "")),
        Attempt("same", lambda: calls.append("second") or ExecutionResult(0, "ok", "")),
    ]
    with pytest.raises(ValueError, match="duplicate"):
        execute_chain(duplicate)
    assert calls == []


def test_exhausted_nonterminal_chain_does_not_allow_hidden_fallback():
    result = execute_chain([Attempt("only", lambda: ExecutionResult(1, "", "failed"))])

    assert result.error is not None
    assert result.error.attempted_executors == ("only",)
    assert result.error.fallback_allowed is False


def test_chain_result_requires_exactly_one_logical_outcome():
    error = ExecutionError(
        code="executor_failed",
        message="Execution failed.",
        detail="No valid output.",
        attempted_executors=("primary",),
        fallback_allowed=False,
    )

    assert ChainResult(output="content").error is None
    assert ChainResult(error=error).output is None
    with pytest.raises(ValueError, match="exactly one"):
        ChainResult()
    with pytest.raises(ValueError, match="exactly one"):
        ChainResult(output="content", error=error)
