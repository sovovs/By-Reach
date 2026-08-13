# By-Reach

By-Reach gives agents a declared, auditable executor route for internet
research. Install it with `pipx install by-reach`, then run:

```bash
by-reach install --env=auto
by-reach doctor --json
```

The default install is read-only. With the user's explicit approval, use
`by-reach install --env=auto --system` to install byCLI and the bundled Skill.

## Webpages

Every webpage read, including static content and raw URLs, is exclusively:

```bash
bycli web read --url "URL" --stdout
```

There is no alternate generic webpage route. If it fails, report the failure.

## Source-specific routes

Twitter uses `twitter-cli` then `bycli twitter search`; Reddit uses `rdt-cli`
then `bycli reddit search`; Bilibili uses `bili-cli` then `bycli bilibili
search`; YouTube uses `yt-dlp` then `bycli youtube search`. Each fallback is
allowed once after a failed or invalid primary result. Facebook, Instagram,
LinkedIn, and XiaoHongShu are byCLI-only. GitHub uses `gh`, RSS uses
`feedparser`, and Exa uses `mcporter` with `exa.web_search_exa`.

Saved Twitter cookies only let diagnostics check setup. A direct `twitter`
command must receive `TWITTER_AUTH_TOKEN` and `TWITTER_CT0` explicitly in its
environment. By-Reach never automates sign-in or reads/injects browser cookies.

Read [installation](install.md), [updates](update.md), and
[troubleshooting](troubleshooting.md) for operational details.
