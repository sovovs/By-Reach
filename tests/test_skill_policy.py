import json
import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "web-routing-pressure-cases.json"
DIRECT_HTTP_COMMAND_PATTERNS = (
    re.compile(r"^\s*(?:[$>]\s*)?curl\s+-", re.IGNORECASE),
    re.compile(r"^\s*(?:[$>]\s*)?wget\s+", re.IGNORECASE),
    re.compile(r"^\s*(?:\w+\s*=\s*)?requests\.get\(", re.IGNORECASE),
    re.compile(r"^\s*(?:\w+\s*=\s*)?urllib\.request", re.IGNORECASE),
)


def _load_cases():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _frontmatter(text: str) -> str:
    lines = text.splitlines()
    assert lines and lines[0] == "---", "SKILL.md must start with YAML frontmatter"
    try:
        closing_index = lines.index("---", 1)
    except ValueError as error:
        raise AssertionError("SKILL.md frontmatter must have a closing delimiter") from error
    return "\n".join(lines[1:closing_index])


def test_web_routing_pressure_cases_are_well_formed():
    cases = _load_cases()
    names = [case.get("name") for case in cases]
    assert names and all(isinstance(name, str) and name.strip() for name in names)
    assert len(names) == len(set(names)), f"case names must be unique: {names}"

    for case in cases:
        assert isinstance(case.get("prompt"), str) and case["prompt"].strip()
        for field in ("required", "forbidden"):
            values = case.get(field)
            assert isinstance(values, list) and values, f"{case['name']}.{field} must be non-empty"
            assert all(isinstance(value, str) and value.strip() for value in values)


def test_skill_contains_required_routes_and_no_forbidden_commands():
    skill_root = ROOT / "by_reach" / "skill"
    skill_file = skill_root / "SKILL.md"
    assert skill_file.is_file(), "expected by_reach/skill/SKILL.md"

    skill_text = skill_file.read_text(encoding="utf-8")
    assert re.search(r"^name:\s*by-reach\s*$", _frontmatter(skill_text), re.MULTILINE)

    markdown_paths = sorted(skill_root.rglob("*.md"))
    assert markdown_paths, "expected Markdown files under by_reach/skill/"
    markdown = {
        path.relative_to(ROOT).as_posix(): path.read_text(encoding="utf-8")
        for path in markdown_paths
    }
    text = "\n".join(markdown.values())
    folded_text = text.casefold()
    cases = _load_cases()

    assert "bycli web read" in text
    missing_required = [
        (case["name"], marker)
        for case in cases
        for marker in case["required"]
        if marker.casefold() not in folded_text
    ]
    assert not missing_required, f"missing required routes: {missing_required}"

    forbidden_markers = {marker for case in cases for marker in case["forbidden"]}
    forbidden_violations = [
        (relative_path, marker)
        for relative_path, contents in markdown.items()
        for marker in forbidden_markers
        if marker.casefold() in contents.casefold()
    ]
    assert not forbidden_violations, f"forbidden Skill routes: {forbidden_violations}"

    direct_http_violations = [
        (relative_path, pattern.pattern)
        for relative_path, contents in markdown.items()
        for line in contents.splitlines()
        for pattern in DIRECT_HTTP_COMMAND_PATTERNS
        if pattern.search(line)
    ]
    assert not direct_http_violations, f"direct HTTP command examples: {direct_http_violations}"
