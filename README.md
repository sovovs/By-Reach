# By-Reach

By-Reach routes AI-agent research to approved source executors and provides
installation and diagnostic commands for those routes.

## The webpage rule

After a task has entered By-Reach routing, **every website or URL read uses
byCLI**:

```bash
bycli web read --url "https://example.com" --stdout
```

This applies equally to static pages, SPAs, articles, raw files, and pages that
do not require sign-in. There is no generic-web fallback. If byCLI cannot read
the target, stop and report the failure.

By-Reach does not automate sign-in, read browser cookies, or inject
credentials. byCLI session use must be explicitly established and authorized by
the user.

## Source routes

| Target | First executor | One fallback, only after failure or invalid content |
| --- | --- | --- |
| Generic webpage | `bycli web read` | none |
| Twitter/X | `twitter-cli` | `bycli twitter search` |
| Reddit | `rdt-cli` | `bycli reddit search` |
| Bilibili | `bili-cli` | `bycli bilibili search` |
| YouTube | `yt-dlp` | `bycli youtube search` |
| V2EX | packaged V2EX API route | `bycli v2ex hot` |
| Xueqiu | packaged Xueqiu API route | `bycli xueqiu search` |
| Facebook, Instagram, LinkedIn, XiaoHongShu | byCLI | none |
| GitHub | `gh` | none |
| RSS | `feedparser` | none |
| Exa search | `mcporter` → `exa.web_search_exa` | none |
| Xiaoyuzhou | By-Reach transcription | none |

Run a source-specific primary once. An empty, challenge, malformed, or
error-shaped result counts as failure; then run the listed byCLI fallback once.
Never replace either route with a generic webpage mechanism.

## Install

```bash
pipx install by-reach
by-reach install --env=auto          # read-only diagnosis
by-reach install --env=auto --system # only after the user authorizes changes
by-reach doctor --json
```

`--system` installs the required byCLI core and registers the By-Reach Skill.
The default command changes nothing. See [the installation guide](docs/install.md)
for the complete safety boundary and optional channel setup.

## Use

```bash
by-reach read "https://example.com"
by-reach doctor --json
by-reach skill --install
```

Persistent configuration is stored in `~/.by-reach/`. Public environment
variables use the `BY_REACH_` prefix. The packaged Skill is named `by-reach`.

For a direct `twitter` command, explicitly set credentials in that command's
environment; saved configuration only helps `by-reach doctor` identify missing
setup:

```bash
export TWITTER_AUTH_TOKEN="..."
export TWITTER_CT0="..."
twitter search "query" -n 10
```

## Development

```bash
pip install -e '.[dev]'
ruff check by_reach tests
mypy by_reach
pytest -q
```

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). This
project is a public fork of
[Panniantong/Agent-Reach](https://github.com/Panniantong/Agent-Reach); its MIT
license and complete upstream Git history are retained.
