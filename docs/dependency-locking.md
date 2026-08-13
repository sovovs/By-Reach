# Dependency Locking Guide

By-Reach uses `constraints.txt` as a reproducible dependency baseline.

## Why

- Keep local/CI dependency graph stable
- Reduce "works on my machine" drift
- Make regression results easier to compare

## Install with constraints

```bash
pip install -c constraints.txt -e '.[dev]'
```

## Update workflow

1. Update `pyproject.toml` dependency ranges as needed.
2. Validate against latest compatible versions locally.
3. Update pinned versions in `constraints.txt`.
4. Run validation:

```bash
pytest -q
ruff check by_reach tests
mypy by_reach
```

5. Open PR with dependency and validation notes.
