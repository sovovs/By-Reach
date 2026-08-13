from pathlib import Path

ROOT = Path(__file__).parents[1]
FORBIDDEN = ("Jina Reader", "r.jina.ai", "Web Reader", "OpenCLI")


def test_generic_web_policy_has_only_bycli():
    from by_reach.executor_policy import POLICIES

    policy = POLICIES["web"]
    assert [item.name for item in policy.executors] == ["bycli"]
    assert policy.executors[0].capability == "web/read"
    assert policy.executors[0].terminal is True


def test_runtime_sources_do_not_contain_forbidden_web_executors():
    source_paths = sorted((ROOT / "by_reach").rglob("*.py"))
    assert source_paths, "expected Python sources under by_reach/"

    violations = []
    for path in source_paths:
        relative_path = path.relative_to(ROOT).as_posix()
        path_text = relative_path.casefold()
        source_text = path.read_text(encoding="utf-8").casefold()
        violations.extend(
            (relative_path, marker)
            for marker in FORBIDDEN
            if marker.casefold() in path_text or marker.casefold() in source_text
        )
    assert not violations, f"forbidden executor references: {violations}"
