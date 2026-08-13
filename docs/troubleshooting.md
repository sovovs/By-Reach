# Troubleshooting

## byCLI is unavailable

Run the read-only diagnostic first:

```bash
by-reach doctor --json
```

If the report says the required byCLI capability is absent, ask the user before
running:

```bash
by-reach install --env=auto --system
```

For every generic webpage, use only `bycli web read --url URL --stdout`. A
failure is terminal for that webpage route; report it instead of trying another
generic reader.

## Twitter source CLI fails

The saved configuration lets the doctor check that credentials exist, but a
direct `twitter` command needs credentials in its own environment:

```bash
export TWITTER_AUTH_TOKEN="..."
export TWITTER_CT0="..."
twitter search "query" -n 10
```

If the source CLI fails or returns invalid content, use its one declared
fallback: `bycli twitter search`. Do not substitute a generic webpage route.

## Xueqiu cookie is missing or expired

After the user authorizes an explicit browser import for that platform:

```bash
by-reach configure --from-browser chrome --platform xueqiu
by-reach doctor --json
```

An unsuccessful Xueqiu API attempt may use the one declared `bycli xueqiu
search` fallback. Do not import unrelated browser data.
