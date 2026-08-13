# Updating By-Reach

Update the distribution with the package manager that installed it:

```bash
pipx upgrade by-reach
# or, in the original environment:
python -m pip install --upgrade by-reach
```

Then verify the installed release and route readiness:

```bash
by-reach version
by-reach doctor --json
```

Only update optional source executors that the user has approved and already
uses. Do not remove user-installed tools or replace a configured session.

For an already-installed YouTube executor, retain its `default` extra when
upgrading so its required runtime dependencies remain present:

```bash
which yt-dlp  >/dev/null 2>&1 && { pipx install --force 'yt-dlp[default]' 2>/dev/null || uv tool install --force 'yt-dlp[default]' 2>/dev/null || python -m pip install -U 'yt-dlp[default]' 2>/dev/null; }
```

This updates only `yt-dlp` when it is already available. It remains the
source-specific YouTube executor and may fall back once to `bycli youtube
search` after failure or invalid content.

The generic webpage rule is unchanged after updates:

```bash
bycli web read --url "https://example.com" --stdout
```

If the `web/read` capability is unavailable, report the failure rather than
using a different webpage reader. Re-run `by-reach install --system` only when
the user authorizes changes and byCLI must be installed or refreshed.
