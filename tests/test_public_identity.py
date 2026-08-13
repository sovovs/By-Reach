import re
from pathlib import Path

import by_reach
import by_reach.core as core

ROOT = Path(__file__).parents[1]


def _manifest_section(manifest: str, name: str) -> str:
    header = re.compile(r"^\[([^]\r\n]+)\]\s*(?:#.*)?$", re.MULTILINE)
    matches = list(header.finditer(manifest))
    sections = [
        manifest[match.end() : matches[index + 1].start() if index + 1 < len(matches) else None]
        for index, match in enumerate(matches)
        if match.group(1) == name
    ]
    assert len(sections) == 1, f"expected exactly one [{name}] section"
    return sections[0]


def _has_exact_string_assignment(section: str, key: str, value: str) -> bool:
    assignment = re.compile(
        rf'^\s*{re.escape(key)}\s*=\s*"{re.escape(value)}"\s*(?:#.*)?$',
        re.MULTILINE,
    )
    return assignment.search(section) is not None


def test_public_package_uses_only_by_reach_names():
    manifest = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project = _manifest_section(manifest, "project")
    scripts = _manifest_section(manifest, "project.scripts")
    wheel = _manifest_section(manifest, "tool.hatch.build.targets.wheel")

    assert _has_exact_string_assignment(project, "name", "by-reach")
    assert _has_exact_string_assignment(scripts, "by-reach", "by_reach.cli:main")
    assert not re.search(r"^\s*agent-reach\s*=", scripts, re.MULTILINE)
    assert re.search(
        r'^\s*packages\s*=\s*\[\s*"by_reach"\s*\]\s*(?:#.*)?$',
        wheel,
        re.MULTILINE,
    )
    assert not re.search(
        r'^\s*packages\s*=\s*\[[^]]*"agent_reach"',
        wheel,
        re.MULTILINE | re.DOTALL,
    )
    assert (ROOT / "by_reach" / "__init__.py").is_file()
    assert not (ROOT / "agent_reach").exists()


def test_public_class_uses_only_by_reach_name():
    assert hasattr(by_reach, "ByReach")
    assert not hasattr(by_reach, "AgentReach")
    assert hasattr(core, "ByReach")
    assert not hasattr(core, "AgentReach")


def test_mcp_extra_declares_the_recovery_dependency_once():
    manifest = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    optional = _manifest_section(manifest, "project.optional-dependencies")
    mcp = re.search(r"^\s*mcp\s*=\s*\[(.*)\]\s*$", optional, re.MULTILINE)
    all_extra = re.search(r"^\s*all\s*=\s*\[(.*)\]\s*$", optional, re.MULTILINE)

    assert mcp is not None
    assert re.fullmatch(r'\s*"mcp\[cli\]>=1\.0"\s*', mcp.group(1))
    assert all_extra is not None
    assert all_extra.group(1).count('"mcp[cli]>=1.0"') == 1
