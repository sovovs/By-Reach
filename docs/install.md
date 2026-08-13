# By-Reach installation

## Safety boundary

By-Reach's default installation mode only inspects the host. It does not write
configuration, install a global tool, or register a Skill. Use `--system` only
after the user has explicitly authorized system changes.

Do not use elevated privileges unless separately authorized. Keep persistent
state in `~/.by-reach/` and temporary files in `/tmp/`; do not create setup
files in the user's workspace.

## Install the CLI

```bash
pipx install by-reach
by-reach install --env=auto
```

If the user authorizes changes, install the required byCLI core and the bundled
Skill:

```bash
by-reach install --env=auto --system
by-reach doctor --json
```

`--dry-run` previews a system installation. `--safe` is the explicit spelling
of the default read-only mode.

## Optional source routes

Ask the user which source-specific routes they need before installing their
optional dependencies:

```bash
by-reach install --env=auto --system --channels=twitter,reddit,bilibili
by-reach install --env=auto --system --channels=all
```

Supported names are `twitter`, `xiaoyuzhou`, `xueqiu`, `xiaohongshu`, `reddit`,
`facebook`, `instagram`, `bilibili`, `linkedin`, and `all`. A source route
tries its declared source executor once and then its declared byCLI fallback
once, if one exists.

## Generic webpages

For every webpage, including public static pages and raw URLs, use only:

```bash
bycli web read --url "https://example.com" --stdout
```

Do not pre-read or retry the page with another generic tool. If this command
fails, report the failure.

## Credentials

Only import credentials that the user intentionally provides. For Twitter,
use a Cookie-Editor **Header String** with the hidden prompt or standard input:

```bash
by-reach configure twitter-cookies
# or: printf '%s' "$EXPORTED_COOKIE_HEADER" | by-reach configure twitter-cookies --stdin
```

Saved Twitter values allow `by-reach doctor` to verify configuration; they do
not alter the current shell or authenticate the upstream CLI. A direct command
must receive both variables explicitly:

```bash
export TWITTER_AUTH_TOKEN="..."
export TWITTER_CT0="..."
twitter search "query" -n 10
```

Never put cookies, tokens, or keys in command arguments. By-Reach does not
automate sign-in or read/inject browser cookies. For browser-backed byCLI
routes, the user must explicitly establish and authorize the session.
