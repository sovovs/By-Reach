"""Shell-free command execution and deterministic executor fallback handling.

``subprocess.run(capture_output=True)`` buffers process output before this module
can inspect it.  The five MiB limit below therefore bounds returned results, not
the child process's peak output memory.  Oversized streams retain their head and
end with a visible truncation marker.

Every supported explicitly configured secret value is redacted: a caller that
declares a value as secret opts into safety over output fidelity. Nonempty values
shorter than four characters or colliding with generated output markers are
rejected before execution; empty values are ignored. Overlapping secrets are
merged and replaced once, so replacement markers are never processed again.
Collision checks include every prefix/suffix boundary overlap that could recreate
a secret next to a generated marker.

Explicit literal-secret matching examines the complete already-buffered stream
in a single pass before its returned head is selected.  This tradeoff is
intentional: bounding first could expose a partial secret at the cut.
URL-credential regexes, which are more complex, only receive bounded tokens;
oversized sensitive-looking tokens are replaced wholesale.

Configured secrets are accepted up to 128 nonempty entries, 8 KiB per value,
and 64 KiB in aggregate.  Over-limit configuration is rejected before an
executor runs; no declared secret is silently dropped.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections import deque
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal

from by_reach.utils.text import scrub_url_credentials

MAX_CAPTURE_BYTES = 5 * 1024 * 1024
TRUNCATION_MARKER = "\n...[truncated]"
_REDACTION_MARKER = "***"
_GENERATED_MARKERS = (_REDACTION_MARKER, TRUNCATION_MARKER)
MAX_JSON_NESTING_DEPTH = 128
MAX_SECRET_COUNT = 128
MIN_SECRET_LENGTH = 4
MAX_SECRET_VALUE_BYTES = 8 * 1024
MAX_SECRET_AGGREGATE_BYTES = 64 * 1024

_ERROR_DETAIL_BYTES = 4096
_STDERR_DETAIL_BYTES = 1024
_MAX_COMPLEX_SCRUB_TOKEN_CHARS = 64 * 1024
_URL_SECRET_HINTS = (
    "token=",
    "bearer=",
    "key=",
    "password=",
    "passwd=",
    "secret=",
    "signature=",
    "sig=",
    "session=",
    "sessionid=",
    "cookie=",
    "credential=",
)
_CLOUDFLARE_PAGE_MARKERS = (
    "<title>attention required",
    "attention required! | cloudflare",
    "<title>just a moment",
    "just a moment...",
)
_CLOUDFLARE_EVIDENCE_MARKERS = (
    "/cdn-cgi/challenge-platform/",
    "cloudflare ray id",
    "checking your browser before accessing",
    "enable javascript and cookies to continue",
)
_UNCONDITIONAL_PAGE_MARKERS = (
    "<title>access denied</title>",
)
_CAPTCHA_CHALLENGE_MARKER = "captcha challenge"
_CAPTCHA_PAGE_CONTEXT_MARKERS = (
    "verify you are human",
    "<form",
    "<iframe",
    "recaptcha",
    "hcaptcha",
)
_ERROR_WRAPPER_CLASS_MARKERS = (
    'class="error-wrapper"',
    'class=\\"error-wrapper\\"',
)
_ERROR_PAGE_CONTEXT_MARKERS = (
    "<title>error</title>",
    "<title>access denied</title>",
    "http status",
    "status-code",
    "data-error-code",
)
_JSON_ERROR_WRAPPER_KEYS = frozenset(
    {"error-wrapper", "challenge-wrapper", "captcha-challenge"}
)

OutputFormat = Literal["text", "json"]


@dataclass(frozen=True)
class ExecutionResult:
    """Raw process status and its safe, bounded output streams."""

    exit_code: int
    stdout: str
    stderr: str
    stdout_truncated: bool = field(
        init=False, default=False, compare=False, repr=False
    )
    stdout_had_content: bool | None = field(
        init=False, default=None, compare=False, repr=False
    )
    stdout_challenge_detected: bool | None = field(
        init=False, default=None, compare=False, repr=False
    )
    stdout_json_valid: bool | None = field(
        init=False, default=None, compare=False, repr=False
    )
    _normalized: bool = field(
        init=False, default=False, compare=False, repr=False
    )

    @property
    def output(self) -> str:
        """Alias for stdout when treating an execution as content production."""

        return self.stdout


@dataclass(frozen=True)
class Attempt:
    """One named executor invocation in a validated fallback chain."""

    name: str
    run: Callable[[], ExecutionResult]
    output_format: OutputFormat = "text"
    terminal: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("executor name must be a non-empty string")
        if not callable(self.run):
            raise TypeError("executor run value must be callable")
        if self.output_format not in ("text", "json"):
            raise ValueError("output_format must be 'text' or 'json'")
        if not isinstance(self.terminal, bool):
            raise TypeError("terminal must be a bool")


@dataclass(frozen=True)
class ExecutionError:
    """Stable, safe failure information for an exhausted executor chain."""

    code: str
    message: str
    detail: str
    attempted_executors: tuple[str, ...]
    fallback_allowed: bool


@dataclass(frozen=True)
class ChainResult:
    """Exactly one logical chain outcome: successful output or a typed error."""

    output: str | None = None
    error: ExecutionError | None = None

    def __post_init__(self) -> None:
        if (self.output is None) == (self.error is None):
            raise ValueError("ChainResult requires exactly one of output or error")


@dataclass(frozen=True)
class _SecretRedactor:
    transitions: tuple[Mapping[str, int], ...]
    failure: tuple[int, ...]
    longest_terminal: tuple[int, ...]

    def redact(self, text: str) -> str:
        if len(self.transitions) == 1:
            return text

        state = 0
        intervals: list[tuple[int, int]] = []
        for index, character in enumerate(text):
            while state and character not in self.transitions[state]:
                state = self.failure[state]
            state = self.transitions[state].get(character, 0)
            match_length = self.longest_terminal[state]
            if match_length:
                intervals.append((index + 1 - match_length, index + 1))
        if not intervals:
            return text

        intervals.sort()
        merged: list[tuple[int, int]] = []
        for start, end in intervals:
            if merged and start < merged[-1][1]:
                previous_start, previous_end = merged[-1]
                merged[-1] = (previous_start, max(previous_end, end))
            else:
                merged.append((start, end))

        chunks: list[str] = []
        cursor = 0
        for start, end in merged:
            chunks.extend((text[cursor:start], _REDACTION_MARKER))
            cursor = end
        chunks.append(text[cursor:])
        return "".join(chunks)


def run_command(
    args: Sequence[str],
    timeout: float | None = None,
    env: Mapping[str, str] | None = None,
    *,
    secret_values: Iterable[str] = (),
) -> ExecutionResult:
    """Run an argument vector without a shell and return scrubbed, bounded streams.

    The caller's argument sequence and environment mapping are copied before the
    subprocess call.  Timeouts and operating-system launch errors are represented
    as nonzero results so an executor chain can apply its declared fallback policy.
    """

    command = _validated_command(args)
    process_env = None if env is None else dict(env)
    redactor = _prepare_secret_redactor(secret_values)

    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=process_env,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = _coerce_text(exc.stdout)
        captured_stderr = _coerce_text(exc.stderr)
        timeout_message = f"Command timed out after {_safe_string(exc.timeout)} seconds."
        stderr = f"{captured_stderr.rstrip()}\n{timeout_message}" if captured_stderr else timeout_message
        return _normalize_execution_result(ExecutionResult(124, stdout, stderr), redactor)
    except FileNotFoundError as exc:
        detail = f"Executable could not be started: {_safe_exception_message(exc)}"
        return _normalize_execution_result(ExecutionResult(127, "", detail), redactor)
    except OSError as exc:
        detail = f"Command could not be started: {_safe_exception_message(exc)}"
        return _normalize_execution_result(ExecutionResult(126, "", detail), redactor)

    return _normalize_execution_result(
        ExecutionResult(completed.returncode, completed.stdout, completed.stderr),
        redactor,
    )


def execute_chain(
    attempts: Sequence[Attempt], *, secret_values: Iterable[str] = ()
) -> ChainResult:
    """Execute attempts in order, stopping at the first valid output.

    There are no implicit retries.  A terminal attempt, when present, must be the
    final declared attempt and prevents any further fallback after it is reached.
    Exhausting any validated chain returns ``fallback_allowed=False`` because this
    result never authorizes fallback beyond the supplied chain.
    """

    chain = _validated_chain(attempts)
    redactor = _prepare_secret_redactor(secret_values)
    attempted_names: list[str] = []
    last_detail = "No executor produced valid output."

    for attempt in chain:
        safe_name = _sanitize_text(attempt.name, redactor, max_bytes=_ERROR_DETAIL_BYTES)
        attempted_names.append(safe_name)
        try:
            raw_result = attempt.run()
        except Exception as exc:
            exception_name = _safe_exception_type_name(exc)
            exception_message = _safe_exception_message(exc)
            raw_detail = f"Executor '{attempt.name}' raised {exception_name}"
            if exception_message:
                raw_detail += f": {exception_message}"
            last_detail = _sanitize_text(
                raw_detail, redactor, max_bytes=_ERROR_DETAIL_BYTES
            )
        else:
            if not isinstance(raw_result, ExecutionResult):
                raw_detail = f"Executor '{attempt.name}' returned an invalid execution result."
                last_detail = _sanitize_text(
                    raw_detail, redactor, max_bytes=_ERROR_DETAIL_BYTES
                )
            else:
                result = _normalize_execution_result(raw_result, redactor)
                invalid_reason = _invalid_output_reason(result, attempt.output_format)
                if invalid_reason is None:
                    return ChainResult(output=result.output)
                raw_detail = f"Executor '{attempt.name}' {invalid_reason}"
                if result.exit_code != 0 and result.stderr.strip():
                    stderr_excerpt = _bound_text(
                        result.stderr.strip(), _STDERR_DETAIL_BYTES
                    )
                    raw_detail += f" stderr: {stderr_excerpt}"
                last_detail = _sanitize_text(
                    raw_detail, redactor, max_bytes=_ERROR_DETAIL_BYTES
                )

        if attempt.terminal:
            break

    error = ExecutionError(
        code="executor_failed",
        message=_sanitize_text("Executor chain failed.", redactor, max_bytes=256),
        detail=last_detail,
        attempted_executors=tuple(attempted_names),
        fallback_allowed=False,
    )
    return ChainResult(error=error)


def _validated_command(args: Sequence[str]) -> list[str]:
    if isinstance(args, (str, bytes)) or not isinstance(args, Sequence):
        raise TypeError("args must be a non-empty sequence of strings")
    if not args:
        raise ValueError("args must contain at least one argument")

    command: list[str] = []
    for arg in args:
        if not isinstance(arg, str):
            raise TypeError("every command argument must be a string")
        if not arg:
            raise ValueError("command arguments must not be empty")
        if "\0" in arg:
            raise ValueError("command arguments must not contain NUL bytes")
        command.append(arg)
    return command


def _validated_chain(attempts: Sequence[Attempt]) -> tuple[Attempt, ...]:
    if isinstance(attempts, (str, bytes)) or not isinstance(attempts, Sequence):
        raise TypeError("attempts must be a non-empty sequence")
    chain = tuple(attempts)
    if not chain:
        raise ValueError("executor chain must contain at least one attempt")
    if any(not isinstance(attempt, Attempt) for attempt in chain):
        raise TypeError("every chain item must be an Attempt")

    names = [attempt.name for attempt in chain]
    if len(names) != len(set(names)):
        raise ValueError("executor chain contains duplicate executor names")
    terminal_positions = [index for index, attempt in enumerate(chain) if attempt.terminal]
    if terminal_positions and terminal_positions != [len(chain) - 1]:
        raise ValueError("a terminal attempt must be the final executor in the chain")
    return chain


def _prepare_secret_redactor(secret_values: Iterable[str]) -> _SecretRedactor:
    secrets = _normalized_secrets(secret_values)
    return _compile_secret_redactor(secrets)


def _normalized_secrets(secret_values: Iterable[str]) -> tuple[str, ...]:
    secrets: set[str] = set()
    count = 0
    aggregate_bytes = 0
    for value in secret_values:
        if not isinstance(value, str):
            raise TypeError("secret values must be strings")
        if not value:
            continue
        count += 1
        if count > MAX_SECRET_COUNT:
            raise ValueError(f"secret count exceeds limit of {MAX_SECRET_COUNT}")
        normalized = _normalize_utf8(value)
        if len(normalized) < MIN_SECRET_LENGTH:
            raise ValueError(
                f"secret values must contain at least {MIN_SECRET_LENGTH} characters"
            )
        if any(
            _secret_collides_with_marker(normalized, marker)
            for marker in _GENERATED_MARKERS
        ):
            raise ValueError("secret value collides with a generated output marker")
        encoded_bytes = len(normalized.encode("utf-8"))
        if encoded_bytes > MAX_SECRET_VALUE_BYTES:
            raise ValueError(
                f"secret value exceeds limit of {MAX_SECRET_VALUE_BYTES} UTF-8 bytes"
            )
        aggregate_bytes += encoded_bytes
        if aggregate_bytes > MAX_SECRET_AGGREGATE_BYTES:
            raise ValueError(
                "secret values exceed aggregate limit of "
                f"{MAX_SECRET_AGGREGATE_BYTES} UTF-8 bytes"
            )
        secrets.add(normalized)
    return tuple(sorted(secrets, key=lambda secret: (-len(secret), secret)))


def _secret_collides_with_marker(secret: str, marker: str) -> bool:
    if secret in marker or marker in secret:
        return True
    for overlap in range(1, min(len(secret), len(marker)) + 1):
        if secret[-overlap:] == marker[:overlap]:
            return True
        if secret[:overlap] == marker[-overlap:]:
            return True
    return False


def _compile_secret_redactor(secrets: tuple[str, ...]) -> _SecretRedactor:
    transitions: list[dict[str, int]] = [{}]
    failure = [0]
    longest_terminal = [0]

    for secret in secrets:
        state = 0
        for character in secret:
            next_state = transitions[state].get(character)
            if next_state is None:
                next_state = len(transitions)
                transitions[state][character] = next_state
                transitions.append({})
                failure.append(0)
                longest_terminal.append(0)
            state = next_state
        longest_terminal[state] = max(longest_terminal[state], len(secret))

    pending: deque[int] = deque(transitions[0].values())
    while pending:
        state = pending.popleft()
        for character, next_state in transitions[state].items():
            pending.append(next_state)
            fallback = failure[state]
            while fallback and character not in transitions[fallback]:
                fallback = failure[fallback]
            failure[next_state] = transitions[fallback].get(character, 0)
            longest_terminal[next_state] = max(
                longest_terminal[next_state],
                longest_terminal[failure[next_state]],
            )

    return _SecretRedactor(
        transitions=tuple(MappingProxyType(node) for node in transitions),
        failure=tuple(failure),
        longest_terminal=tuple(longest_terminal),
    )


def _normalize_execution_result(
    result: ExecutionResult, redactor: _SecretRedactor
) -> ExecutionResult:
    if result._normalized:
        stdout = _sanitize_text(result.stdout, redactor)
        stderr = _sanitize_text(result.stderr, redactor)
        json_valid, parsed_json = _analyze_strict_json(stdout)
        challenge_detected = (
            result.stdout_challenge_detected is True
            or _is_rejected_output(stdout, parsed_json)
        )
        had_content = (
            result.stdout_had_content
            if result.stdout_truncated
            else bool(stdout.strip())
        )
        return _trusted_execution_result(
            result.exit_code,
            stdout,
            stderr,
            stdout_truncated=result.stdout_truncated,
            stdout_had_content=had_content,
            stdout_challenge_detected=challenge_detected,
            stdout_json_valid=json_valid,
        )

    stdout_full = _sanitize_unbounded_text(result.stdout, redactor)
    stderr_full = _sanitize_unbounded_text(result.stderr, redactor)
    json_valid, parsed_json = _analyze_strict_json(stdout_full)
    challenge_detected = _is_rejected_output(stdout_full, parsed_json)
    stdout = _bound_text(stdout_full, MAX_CAPTURE_BYTES)
    stderr = _bound_text(stderr_full, MAX_CAPTURE_BYTES)
    return _trusted_execution_result(
        result.exit_code,
        stdout,
        stderr,
        stdout_truncated=len(stdout_full.encode("utf-8")) > MAX_CAPTURE_BYTES,
        stdout_had_content=bool(stdout_full.strip()),
        stdout_challenge_detected=challenge_detected,
        stdout_json_valid=json_valid,
    )


def _trusted_execution_result(
    exit_code: int,
    stdout: str,
    stderr: str,
    *,
    stdout_truncated: bool,
    stdout_had_content: bool | None,
    stdout_challenge_detected: bool | None,
    stdout_json_valid: bool | None,
) -> ExecutionResult:
    """Attach validation metadata that public construction cannot forge."""

    result = ExecutionResult(exit_code, stdout, stderr)
    object.__setattr__(result, "stdout_truncated", stdout_truncated)
    object.__setattr__(result, "stdout_had_content", stdout_had_content)
    object.__setattr__(
        result, "stdout_challenge_detected", stdout_challenge_detected
    )
    object.__setattr__(result, "stdout_json_valid", stdout_json_valid)
    object.__setattr__(result, "_normalized", True)
    return result


def _sanitize_text(
    text: object,
    redactor: _SecretRedactor,
    *,
    max_bytes: int = MAX_CAPTURE_BYTES,
) -> str:
    return _bound_text(_sanitize_unbounded_text(text, redactor), max_bytes)


def _sanitize_unbounded_text(text: object, redactor: _SecretRedactor) -> str:
    raw = _normalize_utf8(text)

    # The existing URL scrubber is applied token-by-token before configured
    # secrets can alter sensitive query-key names. Complex regexes only
    # see small sensitive-looking tokens; oversized such tokens are conservatively
    # replaced wholesale rather than parsed.
    url_scrubbed = _scrub_url_credentials_by_token(raw)

    # Explicit secrets are then removed from the complete URL-safe value in one
    # trie pass. Generated markers are never rescanned.
    return redactor.redact(url_scrubbed)


def _bound_text(text: str, max_bytes: int) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text

    marker = TRUNCATION_MARKER.encode("utf-8")
    head = encoded[: max_bytes - len(marker)].decode("utf-8", errors="ignore")
    return f"{head}{TRUNCATION_MARKER}"


def _scrub_url_credentials_by_token(text: str) -> str:
    def scrub_token(match: re.Match[str]) -> str:
        token = match.group(0)
        if not _needs_url_scrub(token):
            return token
        if len(token) > _MAX_COMPLEX_SCRUB_TOKEN_CHARS:
            return "***"
        return scrub_url_credentials(token)

    return re.sub(r"\S+", scrub_token, text)


def _needs_url_scrub(text: str) -> bool:
    folded = text.casefold()
    return "@" in text or any(hint in folded for hint in _URL_SECRET_HINTS)


def _safe_string(value: object) -> str:
    try:
        return str(value)
    except Exception:
        return "[unprintable value]"


def _normalize_utf8(value: object) -> str:
    """Return text that always round-trips through strict UTF-8 encoding."""

    return _safe_string(value).encode("utf-8", errors="replace").decode("utf-8")


def _safe_exception_message(exc: Exception) -> str:
    try:
        return str(exc)
    except Exception:
        return "[exception message unavailable]"


def _safe_exception_type_name(exc: Exception) -> str:
    try:
        return type(exc).__name__
    except Exception:
        return "Exception"


def _coerce_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _invalid_output_reason(result: ExecutionResult, output_format: OutputFormat) -> str | None:
    if result.exit_code != 0:
        return f"exited with status {result.exit_code}."
    if result.stdout_had_content is not True:
        return "returned empty output."

    if output_format == "json":
        if result.stdout_truncated:
            return "returned JSON exceeding output limit."
        if result.stdout_json_valid is not True:
            return "returned malformed JSON."

    if result.stdout_challenge_detected is True:
        return "returned a known challenge, access-denied, or error-wrapper response."
    return None


def _analyze_strict_json(output: str) -> tuple[bool, object | None]:
    if _json_exceeds_nesting_limit(output):
        return False, None
    try:
        parsed_json = json.loads(
            output,
            parse_constant=_reject_nonstandard_json_constant,
        )
    except (json.JSONDecodeError, ValueError, TypeError, RecursionError):
        return False, None
    return True, parsed_json


def _json_exceeds_nesting_limit(output: str) -> bool:
    depth = 0
    in_string = False
    escaped = False
    for character in output:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "[{":
            depth += 1
            if depth > MAX_JSON_NESTING_DEPTH:
                return True
        elif character in "]}":
            depth = max(0, depth - 1)
    return False


def _reject_nonstandard_json_constant(constant: str) -> None:
    raise ValueError(f"non-standard JSON constant: {constant}")


def _is_rejected_output(output: str, parsed_json: object | None) -> bool:
    folded = output.casefold()
    if any(marker in folded for marker in _UNCONDITIONAL_PAGE_MARKERS):
        return True
    has_cloudflare_page = any(
        marker in folded for marker in _CLOUDFLARE_PAGE_MARKERS
    )
    has_cloudflare_evidence = any(
        marker in folded for marker in _CLOUDFLARE_EVIDENCE_MARKERS
    )
    if has_cloudflare_page and has_cloudflare_evidence:
        return True
    has_captcha_challenge = _CAPTCHA_CHALLENGE_MARKER in folded
    has_captcha_page_context = any(
        marker in folded for marker in _CAPTCHA_PAGE_CONTEXT_MARKERS
    )
    if has_captcha_challenge and has_captcha_page_context:
        return True
    has_error_wrapper = any(
        marker in folded for marker in _ERROR_WRAPPER_CLASS_MARKERS
    )
    has_error_page_context = any(
        marker in folded for marker in _ERROR_PAGE_CONTEXT_MARKERS
    )
    if has_error_wrapper and has_error_page_context:
        return True
    return parsed_json is not None and _has_json_error_wrapper(parsed_json)


def _has_json_error_wrapper(value: object) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized_key = _normalize_utf8(key).casefold().replace("_", "-")
            if normalized_key in _JSON_ERROR_WRAPPER_KEYS and _is_error_shaped(child):
                return True
            if _has_json_error_wrapper(child):
                return True
    elif isinstance(value, list):
        return any(_has_json_error_wrapper(item) for item in value)
    return False


def _is_error_shaped(value: object) -> bool:
    if value is True:
        return True
    if isinstance(value, (dict, list)):
        return bool(value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    if isinstance(value, str):
        return value.strip().casefold() in {
            "blocked",
            "challenge",
            "denied",
            "error",
            "failed",
            "required",
            "true",
        }
    return False
