# By-Reach v2 Design

## Status

Approved in design review on 2026-08-13. This document defines the `2.0.0b1`
scope for the public `sovovs/By-Reach` fork and its integration into ByClaw.

## Goals

- Rename the Python project and its public runtime surface from Agent Reach to
  By-Reach.
- Make generic webpage acquisition use byCLI exclusively after routing enters
  By-Reach.
- Prefer an explicitly approved source-specific CLI for supported platforms,
  then fall back once to the matching byCLI Adapter when the primary executor
  is unavailable or produces an invalid result.
- Preserve non-web source executors such as Exa, `gh`, RSS, subtitle tools,
  transcription tools, and explicitly approved structured APIs.
- Keep the ByClaw technical Skill ID `agent-reach` stable while changing its
  displayed product name, runtime CLI, diagnostic provider, and routing rules
  to By-Reach.
- Publish a legally attributed public fork to GitHub and a new Python
  distribution to PyPI through Trusted Publishing.

## Non-goals

- Migrating data from `~/.agent-reach`.
- Providing an `agent-reach` CLI, `agent_reach` import, or old environment
  variable compatibility layer.
- Publishing an npm wrapper for By-Reach.
- Letting arbitrary installed CLIs or MCP servers enter routing dynamically.
- Replacing ByClaw's `knowledge-collection` or enterprise-source overlays.
- Enforcing OpenClaw tool permissions such as `web_fetch` denial from inside a
  Skill. That remains an OpenClaw/ByClaw policy-layer concern.

## Public naming contract

The standalone project uses only the new names:

| Surface | Name |
| --- | --- |
| Product and repository | `By-Reach`, `sovovs/By-Reach` |
| PyPI distribution | `by-reach` |
| Python import | `by_reach` |
| CLI | `by-reach` |
| Config directory | `~/.by-reach/` |
| Environment prefix | `BY_REACH_` |
| MCP server | `by-reach` |
| Standalone Skill | `by-reach` |

The standalone package does not install or read legacy names. Historical
entries in `CHANGELOG.md` may retain upstream names when clearly labeled as
upstream history.

ByClaw intentionally retains these stable technical identifiers:

- directory and Skill frontmatter name: `agent-reach`;
- database `skillCode` and `resource_code`: `agent-reach`;
- Skill invocation token: `$agent-reach`.

Their user-visible display name becomes By-Reach, and all runtime commands use
`by-reach`.

## Architecture

### Executor policy registry

Every channel declares an ordered, explicit executor policy. The registry is
the single source of truth for both doctor output and runtime execution.

Executor kinds are:

- `cli`: approved source-specific command-line tools;
- `mcp`: future approved source-specific MCP methods;
- `api`: explicitly approved structured, non-generic-web APIs;
- `bycli`: a named byCLI Adapter or `web/read`;
- `library`: local parsing or transformation such as RSS parsing.

An executor enters the registry only through a reviewed code change with a
capability probe, input mapping, access classification, result validator,
timeout policy, fallback policy, and tests. Runtime discovery cannot promote an
unknown CLI or MCP server into the registry.

### Routing rules

Generic HTTP/HTTPS URLs have exactly one executor:

```text
generic URL -> bycli web/read
```

The implementation invokes byCLI without a shell:

```text
bycli web read --url <URL> --stdout
```

Platform tasks use an approved primary executor when one exists, followed by
at most one byCLI fallback:

```text
Twitter task -> twitter-cli -> bycli twitter Adapter
Reddit task  -> rdt-cli     -> bycli reddit Adapter
Bilibili     -> bili-cli    -> bycli bilibili Adapter
```

The initial approved source executors include `twitter-cli`, `rdt-cli`,
`bili-cli`, `gh`, `yt-dlp`, Exa, RSS parsing, subtitle/transcription tools, and
the structured APIs explicitly retained by the channel policy. Platforms with
no approved primary executor start at byCLI.

Jina Reader, Web Reader MCP, OpenCLI, and generic direct-HTTP webpage
acquisition are forbidden executors. They cannot appear as a primary, fallback,
doctor recommendation, install hint, Skill command, or error recovery path.

### byCLI capability discovery

By-Reach does not require a particular byCLI version number. It verifies
capabilities instead:

1. resolve the `bycli` executable;
2. execute `bycli list -f json`;
3. parse and validate the command manifest;
4. require the task's named Adapter and a read-compatible command;
5. require `web/read` for generic URLs.

The presence of `bycli --version` alone is insufficient. Missing required
capabilities produce an explicit unavailable result; they never trigger a
forbidden fallback.

### Command execution and validation

All subprocesses use argument arrays with shell execution disabled. The common
runner enforces timeouts, captures bounded output, redacts credentials, and
returns a typed execution result.

The common validator distinguishes a valid empty result from execution failure.
Fallback is allowed when the primary executor is missing, times out, exits
non-zero, reports failed authentication, returns empty or malformed output, or
returns a challenge/error page instead of the declared format. A successful
search with zero matches remains a valid result and does not trigger fallback.

byCLI failure is terminal for website tasks. The result records the attempted
executors and sets `fallbackAllowed` to false. No error message may suggest a
forbidden manual command.

### Future MCP executors

The executor interface supports future source-specific MCP services. Each MCP
integration must declare the server and method allowlist, read/write access,
input schema, capability probe, validator, timeout, and fallback behavior.

A source-specific MCP may precede byCLI after review. A generic webpage reader
MCP, including Web Reader MCP, is not eligible. MCP failure cannot become a
hidden fallback after byCLI failure.

## Diagnostics contract

ByClaw capability output moves to schema version 2 and removes the old provider
field:

```json
{
  "schemaVersion": 2,
  "providers": {
    "byReach": {
      "status": "ready",
      "channels": {
        "web": {
          "backends": ["bycli"],
          "activeBackend": "bycli"
        },
        "twitter": {
          "backends": ["twitter-cli", "bycli"],
          "activeBackend": "twitter-cli"
        }
      }
    }
  }
}
```

`providers.agentReach` is not emitted. All in-repository consumers, tests, and
Skill references move to `providers.byReach`. `activeBackend` reports the first
currently available executor; it does not claim an unexecuted fallback has
succeeded.

## Skill model

The standalone By-Reach Skill uses the `by-reach` name and documents the public
executor policy.

ByClaw keeps `middleware/openclaw/skills/agent-reach` as a compatibility ID and
combines two layers:

1. the synchronized By-Reach public routing policy;
2. a ByClaw overlay covering `byclaw-capability-doctor`,
   `knowledge-collection`, enterprise-source routing, root-Agent result
   ownership, fixed image installation, and the prohibition on runtime updates.

Other ByClaw Skills are scanned after synchronization. Technical references to
`agent-reach` remain; product prose becomes By-Reach, executable examples become
`by-reach`, and old repository URLs, imports, environment names, and config
paths are removed.

## Repository and legal provenance

`sovovs/By-Reach` is a public GitHub fork of
`Panniantong/Agent-Reach`, retaining the complete upstream history. The original
MIT license and copyright notice remain intact. Package metadata and README
identify `sovovs` as the By-Reach maintainer and clearly identify the upstream
project.

Upstream sponsor, commercial-contact, and QR-code material that could be
mistaken for By-Reach maintainer information is removed from the derived
project's current documentation. Attribution is preserved without implying
that By-Reach is the upstream project's official successor.

## ByClaw integration

The production Dockerfile replaces all `AGENT_REACH_*` build arguments with
`BY_REACH_*`, downloads a fixed commit archive from `sovovs/By-Reach`, verifies
its SHA-256, installs it, and verifies `by-reach --version` plus doctor output.

The aggregate doctor command invokes `by-reach doctor --json`, renames internal
helpers to By-Reach terminology, emits `providers.byReach`, and keeps the
ByClaw fail-closed webpage override as defense in depth.

The ByClaw work is isolated on `codex/by-reach-integration`, pushed to
`beyonai/ByClaw`, and proposed in a pull request targeting `develop`. Existing
unrelated untracked files in the main worktree are excluded.

## Testing

Development follows red-green-refactor. Baseline pressure cases preserve the
observed failures: choosing Jina for a static page, falling from a generic
browser to `web_fetch`, doctor advertising Jina, and treating empty executor
output as success.

Verification layers are:

1. unit tests for executor order, result validation, capability discovery,
   terminal byCLI failure, and forbidden executor absence;
2. Skill pressure tests before and after the Skill revision;
3. Python 3.10-3.13 and Windows CI, `ruff`, `mypy`, `pytest`, wheel/sdist
   inspection, and clean-environment installation;
4. a real `by-reach` to byCLI read of `https://q.shanyue.tech/`;
5. a ByClaw image build, schema-v2 doctor check, and natural-language tool-trace
   test proving the technical Skill ID routes execution to By-Reach/byCLI;
6. repository-wide static scans for forbidden webpage backends and stale public
   names.

## Publishing

The new PyPI project is `by-reach`. Publishing uses PyPI Trusted Publishing with
GitHub OIDC and a protected `pypi` environment; no long-lived PyPI token is
stored in the repository.

The release sequence is:

1. implement on the feature branch and pass CI;
2. build and inspect wheel and sdist artifacts;
3. push an immutable By-Reach commit;
4. temporarily pin that commit in ByClaw and complete image/behavior tests;
5. tag `v2.0.0b1`;
6. let GitHub Actions publish the prerelease and create a GitHub prerelease;
7. pin the final commit and archive hash in the ByClaw integration branch;
8. push the ByClaw branch and create a PR to `develop`.

Published artifacts are never overwritten. Corrections use a new beta or final
version.
