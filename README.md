# git_autosync

Leak-gated auto commit & push for your GitHub projects.

This is its own project repo (`~/Documents/lab/active/git_autosync`). It holds the
CLI engine today; a PySide6 desktop app that wraps the same engine is planned
(see `HANDOVER.md`).

For every repo listed in `autosync_repos.txt`, the tool:

1. **Stages** all changes (respecting each repo's `.gitignore`).
2. **Scans** with [gitleaks](https://github.com/gitleaks/gitleaks) — both the staged
   changes *and* the existing git history.
3. If a secret is found, that repo is **BLOCKED**: nothing is committed or pushed,
   and the run is flagged. If clean, it **commits** (timestamped message) and **pushes**.

The scan is a hard gate. No clean scan, no push. This is what stops an API key,
password, or token from ever reaching GitHub.

## One-time setup

Install gitleaks (the scanner) — once:

```bash
brew install gitleaks
```

Your repos also need a GitHub `origin` remote already set (the `setup_github.command`
script did this for the five public projects). Repos without a remote are skipped.

## Usage

From this folder (`~/Documents/lab/active/git_autosync`):

```bash
./git_autosync.sh            # sync every repo in the config
./git_autosync.sh --dry-run  # scan + show what WOULD happen; never commits/pushes
./git_autosync.sh --repo sentinel_ai   # just one repo
```

Or simply **double-click `git_autosync.command`** in Finder.

**Tip:** run `--dry-run` first whenever you're unsure — it's completely read-only.

## Choosing which repos are synced

Edit `autosync_repos.txt`. One repo per line; a bare name like `sentinel_ai`
resolves under `~/Documents/lab/active/`. Comment lines start with `#`.

Any repo whose history still contains committed secrets should be left out until
it's cleaned — and even if you add one early, the history scan will keep blocking
it, by design.

## What the auto-commit message looks like

`autosync: 2026-06-27 00:34:00`

If you want a meaningful message instead, just commit that repo by hand
(`git commit -m "..."`) before running autosync — the tool only makes its own
commit when there are still-unstaged changes.

## Logs

Every run appends to `logs/autosync_YYYYMMDD.log`, including the gitleaks output
(secrets are redacted in the log, never written in clear text).

## Exit codes

- `0` — everything synced or nothing to do.
- non-zero — at least one repo was **blocked** or errored. Useful if you later
  wire this into a schedule and want failures to be noticeable.

## Optional: run it on a schedule

This tool was set up to run **on demand**. If you later want a nightly run, it can
be wired into launchd the same way as your `_Admin/backup` job — just ask.

## How it stays safe

- Secrets in *new changes* → blocked before the commit is ever made.
- Secrets already in *history* → blocked before any push.
- gitleaks errors (can't run) → treated as failure, repo skipped — never a silent pass.
- `--dry-run` makes zero changes to your repos or GitHub.
