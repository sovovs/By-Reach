from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_wheel_gate_checks_the_by_reach_distribution_surface() -> None:
    workflow = (ROOT / ".github" / "workflows" / "pytest.yml").read_text(encoding="utf-8")

    assert "by_reach/skill/SKILL.md" in workflow
    assert "by_reach/guides/" in workflow
    assert "by_reach/scripts/" in workflow
    assert "by_reach/skill/references/" in workflow
    assert "/tmp/smoke/bin/by-reach version" in workflow
    assert "import by_reach" in workflow
    assert 'test ! -e "/tmp/smoke/bin/agent-reach"' in workflow
    assert "find_spec('agent_reach') is None" in workflow
    assert "files('agent_reach')" not in workflow
    assert "/tmp/smoke/bin/agent-reach version" not in workflow


def test_release_uses_tagged_pypi_trusted_publishing_without_secrets() -> None:
    workflow_dir = ROOT / ".github" / "workflows"
    assert not (workflow_dir / "publish-pypi.yml").exists()
    workflow = (workflow_dir / "publish.yml").read_text(encoding="utf-8")

    assert "tags:" in workflow
    assert '"v*"' in workflow
    assert "environment: pypi" in workflow
    assert "id-token: write" in workflow
    assert "pypa/gh-action-pypi-publish" in workflow
    assert "contents: write" in workflow
    assert "gh release create" in workflow
    assert "--verify-tag" in workflow
    assert "--prerelease" in workflow
    assert "--generate-notes" in workflow
    assert '[[ "$GITHUB_REF_NAME" == *b* ]]' in workflow
    assert "release_args+=(--prerelease)" in workflow
    assert 'gh release create "$GITHUB_REF_NAME" "${release_args[@]}" dist/*' in workflow
    assert "actions/download-artifact@v4" in workflow
    assert "password:" not in workflow
    assert "PYPI_API_TOKEN" not in workflow
    assert "fetch-depth: 0" in workflow
    assert "git rev-parse \"${GITHUB_REF_NAME}^{commit}\"" in workflow
    assert "origin/main" in workflow
    assert "pytest -q" in workflow
    assert "python -m build" in workflow
    assert "twine check dist/*" in workflow
    assert 'bin/by-reach" version' in workflow
    assert "dist/*.tar.gz" in workflow
    assert "agent-reach" in workflow
    assert "agent_reach" in workflow
