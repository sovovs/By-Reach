---
name: by-reach
description: >
  Use when the user asks to research, search, look up, read, collect, or
  summarize public internet content; gives a URL; or mentions Twitter/X,
  Reddit, Bilibili, XiaoHongShu, Facebook, Instagram, LinkedIn, YouTube,
  GitHub, V2EX, Xueqiu, RSS, Xiaoyuzhou, or Exa.
metadata:
  homepage: https://github.com/sovovs/By-Reach
---

# By-Reach

Use this Skill to select the approved read-only executor. Do not use it for
posting, commenting, liking, authentication, or other write actions.

## Non-negotiable webpage rule

For **every** website, webpage, article, raw URL, static page, SPA, or URL
whose content must be opened or read, use byCLI before obtaining content:

```bash
bycli web read --url "URL" --stdout
```

`web/read` is the sole generic webpage path. Never pre-read, probe, or fall
back to a direct HTTP client, reader proxy, built-in fetcher, legacy adapter,
or generic browser. If byCLI cannot read the target, stop and report that
failure; do not try another webpage mechanism.

Do not automate sign-in, read browser cookies, inject cookies or credentials,
or use a browser session unless the user has explicitly established and
authorized that session for the requested read-only task.

## Routing table

Run `by-reach doctor --json` when availability is unclear. `active_backend`
describes the currently selected executor; it does not prove that a particular
target has content. Treat empty, error-shaped, challenge, or malformed output
as a failed attempt.

| Target | First executor | One permitted fallback |
| --- | --- | --- |
| Any generic webpage or URL | `bycli web read --url URL --stdout` | none |
| Twitter / X | `twitter-cli` | `bycli twitter search` |
| Reddit | `rdt-cli` | `bycli reddit search` |
| Bilibili | `bili-cli` | `bycli bilibili search` |
| YouTube | `yt-dlp` | `bycli youtube search` |
| V2EX | V2EX API through the packaged channel | `bycli v2ex hot` |
| Xueqiu | Xueqiu API through the packaged channel | `bycli xueqiu search` |
| Facebook / Instagram / LinkedIn / XiaoHongShu | byCLI | none |
| GitHub | `gh` CLI | none |
| RSS | `feedparser` library | none |
| Exa search | `mcporter` with `exa.web_search_exa` | none |
| Xiaoyuzhou audio | By-Reach transcription | none |

For a row with a fallback, run the first executor once. Only if it fails or
does not yield meaningful content may you run the listed byCLI command once.
After that fallback fails, stop and report the failure. Do not substitute a
different source-specific CLI or a general webpage tool.

Read the focused reference only when its platform is needed:

- [web](references/web.md) — generic URLs and RSS
- [social](references/social.md) — social and community channels
- [video](references/video.md) — YouTube, Bilibili, Xiaoyuzhou
- [dev](references/dev.md) — GitHub
- [finance](references/finance.md) — V2EX and Xueqiu
- [search](references/search.md) — Exa
- [career](references/career.md) — LinkedIn

Keep transient output in `/tmp/`; keep persistent By-Reach state in
`~/.by-reach/`. Do not create unrelated workspace files.
