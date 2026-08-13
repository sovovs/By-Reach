"""Documentation must preserve the project's explicit auth boundaries."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _policy_documents() -> list[Path]:
    documents = list(ROOT.glob("README*.md"))
    for directory in (
        ROOT / "docs",
        ROOT / "by_reach" / "guides",
        ROOT / "by_reach" / "skill",
    ):
        documents.extend(directory.rglob("*.md"))
    return sorted(set(documents))


def test_xiaohongshu_guidance_never_starts_implicit_login():
    """Do not reintroduce QR or automatic browser-cookie login guidance."""
    xhs_markers = ("xiaohongshu", "小红书", "小紅書", "xhs")
    legacy_auth_markers = (
        "扫码",
        "二维码",
        "qr login",
        "qr scan",
        "qrcode",
        "ブラウザからcookieを自動抽出",
        "브라우저에서 cookie 자동 추출",
    )
    forbidden_commands = (
        "xhs " + "login",
        "get_login_" + "qrcode",
    )

    violations = []
    for path in _policy_documents():
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        for command in forbidden_commands:
            if command in lowered:
                violations.append(f"{path.relative_to(ROOT)}: {command}")
        for line_number, line in enumerate(lowered.splitlines(), 1):
            if not any(marker in line for marker in xhs_markers):
                continue
            if any(marker in line for marker in legacy_auth_markers):
                violations.append(
                    f"{path.relative_to(ROOT)}:{line_number}: {line.strip()}"
                )

    assert not violations, "\n".join(violations)


def test_twitter_operational_docs_explain_the_environment_boundary():
    """Saved cookies help doctor only; direct twitter commands need env vars."""
    operational_docs = (
        ROOT / "README.md",
        ROOT / "docs" / "README_en.md",
        ROOT / "docs" / "README_ja.md",
        ROOT / "docs" / "README_ko.md",
        ROOT / "docs" / "cookie-export.md",
        ROOT / "docs" / "install.md",
        ROOT / "docs" / "troubleshooting.md",
        ROOT / "by_reach" / "guides" / "setup-twitter.md",
    )

    for path in operational_docs:
        text = path.read_text(encoding="utf-8")
        assert "TWITTER_AUTH_TOKEN" in text, path.relative_to(ROOT)
        assert "TWITTER_CT0" in text, path.relative_to(ROOT)

    twitter_guide = (
        ROOT / "by_reach" / "guides" / "setup-twitter.md"
    ).read_text(encoding="utf-8")
    assert "`doctor` 不会执行" in twitter_guide
    assert "不会修改当前 Shell" in twitter_guide
    assert "Export → Header String" in twitter_guide
    assert "cookie JSON" not in twitter_guide
    assert "复制全部" not in twitter_guide
    assert "by-reach configure twitter-cookies" in twitter_guide
    assert "agent-reach" not in twitter_guide
    assert ".agent-reach" not in twitter_guide
    assert "Agent Reach" not in twitter_guide

    for expected in (
        "--sync-legacy-twitter",
        "~/.by-reach/config.yaml",
        "~/.config/xfetch/session.json",
        "~/.config/bird/credentials.env",
    ):
        assert expected in twitter_guide
    assert "默认只写" in twitter_guide
    assert "不会自动删除" in twitter_guide

    rendered_as_verified = (
        "✅ Twitter/X tweets",
        "✅ Twitter/Xツイート",
        "✅ Twitter/X 트윗",
    )
    all_text = "\n".join(
        path.read_text(encoding="utf-8") for path in _policy_documents()
    )
    assert not any(claim in all_text for claim in rendered_as_verified)


def test_localized_readmes_keep_current_bilibili_route():
    """Translations must not revive the retired yt-dlp Bilibili route."""
    readmes = (
        ROOT / "README.md",
        ROOT / "docs" / "README_en.md",
        ROOT / "docs" / "README_ja.md",
        ROOT / "docs" / "README_ko.md",
    )

    for path in readmes:
        text = path.read_text(encoding="utf-8")
        assert "bilibili.py     → yt-dlp" not in text, path.relative_to(ROOT)
        assert "YouTube + Bilibili" not in text, path.relative_to(ROOT)
        assert "bili-cli" in text, path.relative_to(ROOT)


def test_localized_readmes_do_not_advertise_retired_channels():
    """Japanese and Korean docs must match the channels shipped by the CLI."""
    for path in (ROOT / "docs" / "README_ja.md", ROOT / "docs" / "README_ko.md"):
        text = path.read_text(encoding="utf-8").lower()
        assert "douyin" not in text, path.relative_to(ROOT)
        assert "weibo" not in text, path.relative_to(ROOT)


def test_public_guidance_never_installs_the_unrelated_pypi_package():
    """The PyPI name is owned by another project; GitHub URLs are required."""
    candidates = _policy_documents() + [
        ROOT / "by_reach" / "integrations" / "mcp_server.py",
    ]
    bare_install = re.compile(
        r"\bpip\s+install(?:\s+--upgrade)?\s+['\"]?agent-reach(?:\[[^\]]+\])?\b",
        re.IGNORECASE,
    )
    violations = []
    for path in candidates:
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if bare_install.search(line) and (
                "github.com/Panniantong/agent-reach" not in line
            ):
                violations.append(
                    f"{path.relative_to(ROOT)}:{line_number}: {line.strip()}"
                )

    assert not violations, "\n".join(violations)


def test_public_guidance_never_puts_secrets_in_process_arguments():
    """Operational docs should use hidden prompts or stdin for credentials."""
    forbidden = (
        'by-reach configure twitter-cookies "',
        "by-reach configure twitter-cookies '",
        'by-reach configure xhs-cookies "',
        "by-reach configure xhs-cookies '",
        "by-reach configure groq-key gsk_",
        "by-reach configure openai-key sk-",
        "by-reach configure github-token gh",
        "by-reach configure proxy http",
    )
    violations = []
    for path in _policy_documents():
        text = path.read_text(encoding="utf-8")
        for marker in forbidden:
            if marker in text:
                violations.append(f"{path.relative_to(ROOT)}: {marker}")

    assert not violations, "\n".join(violations)


def test_current_user_guidance_has_no_retired_webpage_executor():
    """Current docs must agree with the terminal byCLI webpage policy.

    Changelog and design records deliberately retain historical terminology;
    this test covers only documentation that instructs a user or operator.
    """
    documents = [
        ROOT / "README.md",
        ROOT / "llms.txt",
        ROOT / "CONTRIBUTING.md",
        ROOT / "docs" / "install.md",
        ROOT / "docs" / "update.md",
        ROOT / "docs" / "troubleshooting.md",
        ROOT / "docs" / "cookie-export.md",
        ROOT / "docs" / "README_en.md",
        ROOT / "docs" / "README_ja.md",
        ROOT / "docs" / "README_ko.md",
        *sorted((ROOT / "by_reach" / "guides").glob("*.md")),
    ]
    retired = ("Jina Reader", "r.jina.ai", "Web Reader", "OpenCLI", "web_fetch")
    violations = []
    for path in documents:
        text = path.read_text(encoding="utf-8")
        for marker in retired:
            if marker.lower() in text.lower():
                violations.append(f"{path.relative_to(ROOT)}: {marker}")

    assert not violations, "\n".join(violations)


def test_video_reference_has_content_level_youtube_fallbacks():
    """Version-only health must not be presented as proof subtitles work."""
    text = (
        ROOT / "by_reach" / "skill" / "references" / "video.md"
    ).read_text(encoding="utf-8")
    assert "yt-dlp" in text
    assert "bycli youtube search" in text
    assert "by-reach transcribe" in text


def test_skill_routes_finance_through_declared_bycli_fallback():
    finance = ROOT / "by_reach" / "skill" / "references" / "finance.md"
    text = finance.read_text(encoding="utf-8")
    assert "bycli xueqiu search" in text
    assert "不得自行发起网页 HTTP 请求" in text
