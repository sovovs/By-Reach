import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "test.sh"


def test_integration_script_has_valid_shell_syntax(bash_executable):
    subprocess.run([bash_executable, "-n", SCRIPT.name], check=True, cwd=ROOT)


def test_integration_script_exercises_the_current_cli_contract():
    text = SCRIPT.read_text(encoding="utf-8")

    assert 'pip install --quiet -c "$REPO_ROOT/constraints.txt"' in text
    assert 'TEST_DIR=$(cd "$TEST_DIR" && pwd -P)' in text
    assert 'export HOME="$TEST_DIR/home"' in text
    assert "sys.version_info >= (3, 10)" in text
    assert 'PYTHON_CMD=("$REPO_ROOT/.venv/bin/python")' in text
    assert 'venv/Scripts/activate' in text
    assert "by-reach install --env=auto --safe" in text
    assert "by-reach install --env=auto --system --dry-run" in text
    assert "by-reach doctor --json" in text
    assert 'pytest "$REPO_ROOT/tests" -q' in text

    nonexistent_commands = (
        "by-reach read ",
        "by-reach search ",
        "by-reach search-github ",
        "by-reach search-twitter ",
        "by-reach search-reddit ",
        "by-reach search-youtube ",
        "by-reach search-bilibili ",
        "by-reach search-xhs ",
    )
    assert not any(command in text for command in nonexistent_commands)
