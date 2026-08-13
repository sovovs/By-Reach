---
name: by-reach
description: >
  Use when the user asks to research, search, look up, read, collect, or
  summarize public internet content; gives a URL; or mentions a supported
  social, video, developer, finance, RSS, podcast, or Exa source.
metadata:
  homepage: https://github.com/sovovs/By-Reach
---

# By-Reach

This English reference has the same policy as `SKILL.md`. The canonical generic
URL command is:

```bash
bycli web read --url "URL" --stdout
```

Use this command for every webpage read. `web/read` has no alternate generic
executor. Do not obtain the page through a direct HTTP client, reader proxy,
built-in fetcher, legacy adapter, or generic browser before or after byCLI.
If it fails, report the failure.

For a source-specific route, use its declared first executor once and then its
listed byCLI fallback once only: `twitter-cli` → `bycli twitter search`;
`rdt-cli` → `bycli reddit search`; `bili-cli` → `bycli bilibili search`;
`yt-dlp` → `bycli youtube search`; V2EX API → `bycli v2ex hot`; Xueqiu API →
`bycli xueqiu search`. Facebook, Instagram, LinkedIn, and XiaoHongShu are
byCLI-only. GitHub uses `gh`; RSS uses `feedparser`; Exa uses `mcporter` with
`exa.web_search_exa`; Xiaoyuzhou uses By-Reach transcription.

Never automate sign-in, read or inject cookies, or expose credentials. See the
matching file in `references/` for safe command examples and stop after an
unsuccessful terminal route.
