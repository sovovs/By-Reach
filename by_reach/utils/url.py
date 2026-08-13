"""Security helpers for untrusted URLs."""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable, Iterable
from urllib.parse import urlsplit

import idna

_BLOCKED_PUBLIC_FETCH_HOSTS = {
    "home.arpa",
    "instance-data",
    "internal",
    "ip6-localhost",
    "ip6-loopback",
    "lan",
    "local",
    "localdomain",
    "localhost",
    "metadata.google.internal",
}
_BLOCKED_PUBLIC_FETCH_SUFFIXES = (
    ".home.arpa",
    ".internal",
    ".lan",
    ".local",
    ".localdomain",
    ".localhost",
)
_DNS_SEPARATOR_TRANSLATION = str.maketrans(
    {"\u3002": ".", "\uff0e": ".", "\uff61": "."}
)

Resolver = Callable[..., Iterable[object]]


def _literal_ip_address(
    host: str,
) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Parse canonical and legacy IPv4 literal spellings without DNS."""
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass

    try:
        packed = socket.inet_aton(host)
    except OSError:
        return None
    return ipaddress.IPv4Address(packed)


def normalize_public_http_url(url: str) -> str:
    """Normalize a URL or reject targets that are not clearly public HTTP(S)."""
    candidate = str(url or "").strip()
    if (
        not candidate
        or "\\" in candidate
        or any(
            character.isspace() or ord(character) < 0x20 or ord(character) == 0x7F
            for character in candidate
        )
    ):
        raise ValueError("only public HTTP(S) URLs are allowed")
    if "://" not in candidate:
        candidate = f"https://{candidate}"

    try:
        parsed = urlsplit(candidate)
        # Accessing the port rejects malformed or out-of-range authorities.
        port = parsed.port
    except (TypeError, ValueError):
        raise ValueError("only public HTTP(S) URLs are allowed") from None

    if (
        parsed.scheme.lower() not in {"http", "https"}
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("only public HTTP(S) URLs are allowed")

    host = _canonical_public_host(parsed.hostname or "")
    netloc = f"[{host}]" if ":" in host else host
    if port is not None:
        netloc = f"{netloc}:{port}"
    return parsed._replace(scheme=parsed.scheme.lower(), netloc=netloc).geturl()


def resolve_public_http_url(
    url: str, *, resolver: Resolver | None = None
) -> str:
    """Normalize a public URL and perform a fail-closed initial DNS preflight.

    This validates only the addresses returned before byCLI starts navigation.
    Redirects, subresources, and DNS-to-connection pinning remain the
    responsibility of byCLI's browser/network security boundary.
    """

    normalized = normalize_public_http_url(url)
    parsed = urlsplit(normalized)
    host = parsed.hostname or ""
    if _literal_ip_address(host) is not None:
        return normalized

    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme == "https" else 80
    selected_resolver = socket.getaddrinfo if resolver is None else resolver

    try:
        records = selected_resolver(host, port, type=socket.SOCK_STREAM)
        if records is None:
            raise ValueError

        found_address = False
        for record in records:
            if not isinstance(record, (tuple, list)) or len(record) < 5:
                raise ValueError
            family = record[0]
            sockaddr = record[4]
            if family not in (socket.AF_INET, socket.AF_INET6):
                raise ValueError
            if not isinstance(sockaddr, (tuple, list)) or not sockaddr:
                raise ValueError
            address_text = sockaddr[0]
            if not isinstance(address_text, str) or "%" in address_text:
                raise ValueError
            address = ipaddress.ip_address(address_text)
            if (
                (family == socket.AF_INET and address.version != 4)
                or (family == socket.AF_INET6 and address.version != 6)
                or not address.is_global
            ):
                raise ValueError
            found_address = True
        if not found_address:
            raise ValueError
    except Exception:
        raise ValueError("only public HTTP(S) URLs are allowed") from None

    return normalized


def _canonical_public_host(raw_host: str) -> str:
    """Return the ASCII hostname whose resolver meaning was validated."""

    host = raw_host.translate(_DNS_SEPARATOR_TRANSLATION).lower()
    if not host or "%" in host:
        raise ValueError("only public HTTP(S) URLs are allowed")

    if host.endswith("."):
        host = host[:-1]
        if not host or host.endswith("."):
            raise ValueError("only public HTTP(S) URLs are allowed")

    literal_address = _literal_ip_address(host)
    if literal_address is not None:
        if not literal_address.is_global:
            raise ValueError("only public HTTP(S) URLs are allowed")
        return str(literal_address)

    if ":" in host:
        raise ValueError("only public HTTP(S) URLs are allowed")

    if "." not in host:
        raise ValueError("only public HTTP(S) URLs are allowed")

    try:
        canonical = idna.encode(
            host,
            uts46=True,
            transitional=False,
            std3_rules=True,
        ).decode("ascii").lower()
    except (idna.IDNAError, UnicodeError):
        raise ValueError("only public HTTP(S) URLs are allowed") from None

    canonical_literal = _literal_ip_address(canonical)
    if canonical_literal is not None:
        if not canonical_literal.is_global:
            raise ValueError("only public HTTP(S) URLs are allowed")
        return str(canonical_literal)

    if (
        len(canonical) > 253
        or canonical in _BLOCKED_PUBLIC_FETCH_HOSTS
        or canonical.endswith(_BLOCKED_PUBLIC_FETCH_SUFFIXES)
    ):
        raise ValueError("only public HTTP(S) URLs are allowed")
    return canonical


def domain_matches(host: str, *domains: str) -> bool:
    """Match a hostname/cookie domain exactly or as a real subdomain."""
    normalized_host = str(host or "").lower().lstrip(".").rstrip(".")
    if not normalized_host:
        return False
    for domain in domains:
        allowed = domain.lower().lstrip(".").rstrip(".")
        if normalized_host == allowed or normalized_host.endswith("." + allowed):
            return True
    return False


def host_matches(url: str, *domains: str) -> bool:
    """Return whether *url* has an exact allowed host or a real subdomain.

    Only HTTP(S) URLs without userinfo are accepted. Using ``hostname`` rather
    than substring matching prevents lookalikes such as ``x.com.evil.test`` and
    userinfo disguises such as ``x.com@evil.test``.
    """
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        # ``hostname`` is permissive: malformed or out-of-range ports only
        # raise when ``port`` is accessed. Force that validation here so
        # hostile authorities fail closed.
        _ = parsed.port
    except (TypeError, ValueError):
        return False

    if parsed.scheme.lower() not in {"http", "https"}:
        return False
    if not host or parsed.username is not None or parsed.password is not None:
        return False

    return domain_matches(host, *domains)
