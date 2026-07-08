# git_autosync

Leak-gated auto commit & push for your GitHub projects.

This is its own project repo (`~/Documents/lab/active/git_autosync`). It holds the
CLI engine (`git_autosync.sh`, tested and canonical) plus a PySide6 desktop GUI
(`app/`) that wraps the same engine — see `HANDOVER.md` for the full design notes.

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

Your repos also need a GitHub `origin` remote already set (either via the
`setup_github.command` script, or via this tool's own `--create-remote` flag /
the GUI's **Create GitHub repo...** button — see below). Repos without a remote
are skipped during normal syncs.

If you want to use `--create-remote` (publish a new repo), you also need the
[GitHub CLI](https://cli.github.com), authenticated:

```bash
brew install gh
gh auth login
```

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

## Publishing a new project to GitHub

A repo with no `origin` remote is normally just **SKIP**ped — autosync never
decides on its own to make something public. To actually publish one, pass
`--create-remote`:

```bash
./git_autosync.sh --repo my_new_project --create-remote private   # or: public
```

This still runs the full leak-gate first (staged changes + history). Only if
that's clean does it call `gh repo create --source=. --remote=origin --push`.
If a secret is found, nothing is created or pushed — same as a normal sync.
The repo also needs to already be listed in `autosync_repos.txt` (the GUI's
**Create GitHub repo...** dialog adds it for you automatically).

## What the auto-commit message looks like

`autosync: 2026-06-27 00:34:00`

If you want a meaningful message instead, just commit that repo by hand
(`git commit -m "..."`) before running autosync — the tool only makes its own
commit when there are still-unstaged changes.

## Logs

Every run appends to `logs/autosync_YYYYMMDD.log`, including the gitleaks output
(secrets are redacted in the log, never written in clear text).

Override the log location with `AUTOSYNC_LOG_DIR` (the GUI always does this,
pointing at `~/Library/Application Support/git_autosync/logs/`).

## Last-sync state

After any **real** (non-dry-run) invocation, the script writes a timestamp to
`last_sync.txt` in `AUTOSYNC_STATE_DIR` (defaults to the script's own folder;
the GUI points this at its Application Support folder). Dry-runs never touch
it. This is how the GUI's "Last sync" / "Next sync" status bar stays accurate
regardless of whether a sync was triggered by hand or by the background
schedule.

## Exit codes

- `0` — everything synced or nothing to do.
- non-zero — at least one repo was **blocked** or errored. Useful if you later
  wire this into a schedule and want failures to be noticeable.

## Running it on a schedule

The easiest way is the GUI's **Schedule sync...** button (see below) — it
installs a `launchd` LaunchAgent for you with no manual plist editing.

To do it by hand instead, install a LaunchAgent the same way as
`_Admin/backup`'s nightly job, pointing `ProgramArguments` at this script and
setting `AUTOSYNC_CONFIG` / `AUTOSYNC_LOG_DIR` / `AUTOSYNC_STATE_DIR` /
`GITLEAKS_CMD` / `GH_CMD` in `EnvironmentVariables` (Finder/launchd processes
don't inherit your shell's `PATH`, so these need to be explicit, ideally as
absolute paths — see `app/scheduler.py` for a working example, including both
`StartInterval` and `StartCalendarInterval` styles).

## How it stays safe

- Secrets in *new changes* → blocked before the commit is ever made.
- Secrets already in *history* → blocked before any push.
- gitleaks errors (can't run) → treated as failure, repo skipped — never a silent pass.
- `--dry-run` makes zero changes to your repos or GitHub.
- `--create-remote` (publishing a new repo) runs through the same gate before
  `gh repo create --push` is ever called — a detected secret blocks repo
  creation entirely, not just the push.

## Desktop app (GUI)

A PySide6 GUI wraps the same engine — it never reimplements the leak-gate
logic, it just shells out to `git_autosync.sh` (and, for repo creation,
`gh`) via `QProcess`.

**Main window:**

- **Repo checklist** with status badges after each run (✅ Synced · ⛔ Blocked ·
  ⏭ Skipped · ⚠️ Error · ➖ No-op), sourced from `autosync_repos.txt`.
- **Dry-run (safe)** / **Sync now** — Sync now is disabled until gitleaks is
  found, with an install hint shown instead.
- **Edit repo list** — opens `autosync_repos.txt` in your default editor.
- **Create GitHub repo...** — lists local projects under
  `~/Documents/lab/active/` that don't have a GitHub remote yet (plus a
  "Browse..." option for anything else), lets you pick a repo name and
  visibility (private by default), adds it to the repo list, then runs the
  same `--create-remote` flow described above. Shows the new repo's URL on
  success.
- **Open logs** — reveals the log folder in Finder.
- **Tooltips: on/off** — toggles explanatory tooltips on every control.
- **Documentation** — renders this README in an in-app viewer (no external
  app like Pages or VS Code involved), falling back to a short in-app summary
  if the file is missing from the bundle.
- **Schedule sync...** — opens a dialog to configure a background `launchd`
  job: either "run every" (15 min / 30 min / 1h / 6h / 12h / 24h) or "run
  daily at" a specific time, plus whether to also run once immediately when
  enabled. Shows the current schedule and lets you update or disable it.
- **Last sync / Next sync** — shown in the bottom status bar; "Last sync"
  reflects the engine's own state file (so it's correct whether the last run
  was manual or scheduled), "Next sync" is computed from the active schedule,
  or reads "not scheduled" if none is set.

Run from source:

```bash
uv venv .venv && source .venv/bin/activate
uv pip install -r requirements.txt
python -m app.main
```

Build the standalone `.app` (installs to `/Applications`):

```bash
./build_app.sh
```

Notes:

- The GUI's config, logs, and last-sync state live in
  `~/Library/Application Support/git_autosync/` (the packaged bundle is
  read-only), seeded from `autosync_repos.txt` on first run.
- The packaged app resolves `gitleaks` / `git` / `gh` explicitly (checking
  `/opt/homebrew/bin`, `/usr/local/bin`, then `PATH`) because Finder-launched
  apps don't inherit your shell's PATH. The same resolution is baked into any
  installed background schedule, so it keeps working when launched headlessly
  by launchd too.
- The app icon (`packaging/icon.icns`) is generated by `packaging/make_icon.py`
  (a sync-cycle glyph — this tool's job is syncing repos to GitHub; the
  leak-gate is a safety step inside that, not the headline feature). Regenerate
  it with `python packaging/make_icon.py && cd packaging && iconutil -c icns
  icon.iconset -o icon.icns && rm -rf icon.iconset` after editing the script.
- The app is ad-hoc signed (`codesign --force --deep -s -`), so the first launch
  needs right-click → Open (no Apple Developer ID / notarization yet).

## Git identity

Commits made by this tool (and everywhere else in this lab workspace) use a
pseudonymous identity, not a real name/email — `git config --global user.name
/ user.email` should already be set to the `Netrunner3000` GitHub noreply
identity. Don't hardcode a real name/email anywhere in this project.
