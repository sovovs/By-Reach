# Contributing to By-Reach

Thanks for contributing. By-Reach is a fork that retains the complete Git
history and MIT license of
[Panniantong/Agent-Reach](https://github.com/Panniantong/Agent-Reach).

## Development setup

```bash
git clone https://github.com/YOUR_USERNAME/By-Reach.git
cd By-Reach
python -m pip install -e '.[dev]'
```

Before opening a pull request, run:

```bash
ruff check by_reach tests
mypy by_reach
pytest -q
```

## Routing changes

Keep executor order declarative in `by_reach/executor_policy.py` and cover new
behavior with tests. Generic website reads are terminal byCLI operations:

```bash
bycli web read --url "URL" --stdout
```

Do not introduce an alternate generic webpage reader, a direct-HTTP retry, or
a legacy executor alias. A source-specific primary may fall back once to the
declared byCLI capability only when its result fails validation.

## Pull requests

- Keep changes focused and include tests for behavior changes.
- Update user-facing docs when public behavior changes.
- Never add secrets, cookies, tokens, or private endpoints.
- Preserve the MIT license and upstream attribution.
