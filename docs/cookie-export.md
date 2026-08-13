# Cookie export

Only handle credentials the user deliberately exports and supplies. By-Reach
does not sign users in, inspect browser profiles, or inject a browser session.

For Twitter, the user may export a **Header String** with Cookie-Editor and
provide it to the hidden prompt:

```bash
by-reach configure twitter-cookies
```

For non-interactive use, send the same value over standard input:

```bash
printf '%s' "$EXPORTED_COOKIE_HEADER" | by-reach configure twitter-cookies --stdin
```

Do not put a cookie or token in a process argument, shell history, issue, or
chat transcript. Configuration is stored under `~/.by-reach/` with owner-only
permissions.

Twitter configuration is diagnostic metadata only. It does not modify the
current shell. Direct upstream commands require explicit environment variables:

```bash
export TWITTER_AUTH_TOKEN="..."
export TWITTER_CT0="..."
twitter search "query" -n 10
```

For byCLI-backed website routes, an existing session may be used only when the
user explicitly established and authorized it for the requested read-only task.
