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
   and the run is flagged. If clean, it **commits** and **pushes**.

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

If you want to publish new repos, you also need the
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

The GUI's **Edit list** button opens this file in your default editor. The app
automatically reloads the list the moment you save the file — no restart needed.

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
If a secret is found, nothing is created or pushed.
The repo also needs to already be listed in `autosync_repos.txt` (the GUI's
**Create GitHub repo...** dialog adds it for you automatically).

## Custom commit messages

By default autosync generates a timestamped message:
`autosync: 2026-06-27 00:34:00`

You can override this in two ways:

- **GUI:** type a message in the commit message field before clicking Sync.
- **CLI:** set the `AUTOSYNC_COMMIT_MSG` environment variable:
  ```bash
  AUTOSYNC_COMMIT_MSG="refactor: tidy up" ./git_autosync.sh --repo my_repo
  ```

If you want a meaningful message but don't want to type it every time, just commit
by hand (`git commit -m "..."`) before running autosync — the tool only makes its
own commit when there are un-committed changes.

## Logs

Every run appends to `logs/autosync_YYYYMMDD.log`, including the gitleaks output
(secrets are redacted in the log, never written in clear text).

Override the log location with `AUTOSYNC_LOG_DIR` (the GUI always does this,
pointing at `~/Library/Application Support/git_autosync/logs/`).

## Last-sync state

After any **real** (non-dry-run) invocation, the script writes a timestamp to
`last_sync.txt` in `AUTOSYNC_STATE_DIR` (defaults to the script's own folder;
the GUI points this at its Application Support folder). Dry-runs never touch
it. This is how the GUI's status bar stays accurate regardless of whether a sync
was triggered by hand or by the background schedule.

## Exit codes

- `0` — everything synced or nothing to do.
- non-zero — at least one repo was **blocked** or errored.

## Running it on a schedule

The easiest way is the GUI's **Schedule sync...** button — it installs a `launchd`
LaunchAgent for you with no manual plist editing.

To do it by hand instead, install a LaunchAgent pointing `ProgramArguments` at
this script and set `AUTOSYNC_CONFIG` / `AUTOSYNC_LOG_DIR` / `AUTOSYNC_STATE_DIR` /
`GITLEAKS_CMD` / `GH_CMD` in `EnvironmentVariables` as explicit absolute paths
(Finder/launchd processes don't inherit your shell's `PATH`) — see
`app/scheduler.py` for a working example.

## How it stays safe

- Secrets in *new changes* → blocked before the commit is ever made.
- Secrets already in *history* → blocked before any push.
- gitleaks errors (can't run) → treated as failure, repo skipped — never a silent pass.
- `--dry-run` makes zero changes to your repos or GitHub.
- `--create-remote` runs through the same gate before `gh repo create --push` is
  ever called — a detected secret blocks repo creation entirely, not just the push.

## Handling false positives

If gitleaks flags something that isn't a real secret, you can add its fingerprint
to a per-repo `.gitleaksignore` file. The GUI makes this easy:

1. Run a dry-run — the blocked repo's fingerprint appears in the **Output** pane.
2. Open the app's **Ignore** dialog (from the leak report at the bottom of the
   output pane) and click **Add last finding**.
3. Run a dry-run again to confirm the repo is no longer blocked.

Only add entries you are certain are false positives — ignoring a real secret is
a security risk.

You can also manage `.gitleaksignore` by hand: one fingerprint per line, in the
format gitleaks uses (`<commit>:<file>:<rule>:<line>`).

---

## Desktop app (GUI)

A PySide6 GUI wraps the same engine — it never reimplements the leak-gate logic,
it just shells out to `git_autosync.sh` (and, for repo creation, `gh`) via
`QProcess`.

### Main window

**Repositories section:**

- **Repo list** — one row per repo in `autosync_repos.txt`. Each row shows:
  - The repo name.
  - A colored **status badge** after each run:
    `✓ Synced` (green) · `✕ Blocked` (red) · `⊘ Skipped` (grey) ·
    `⚠ Error` (amber) · `No changes` (grey).
  - A **🕒 stale indicator** (amber) when the repo hasn't been synced in
    3+ days, or has never been synced.
  - **Dry-run** button — scans just this repo, never commits or pushes.
  - **Sync** button — syncs just this repo after the leak-gate clears it.
    Shows a diff preview of pending changes before you confirm.
  - **Publish to GitHub…** button (replaces Sync) for repos with no remote yet.
  - **Privacy…** button — toggle the repo between public and private on GitHub
    (`gh repo edit --visibility …`).
- **Auto-reload** — the list refreshes automatically when you save
  `autosync_repos.txt`, with no restart needed (`QFileSystemWatcher`).

**Commit message field:**

Type a custom commit message before syncing. Leave it blank to use the default
timestamped message (`autosync: YYYY-MM-DD HH:MM:SS`). The message is passed via
the `AUTOSYNC_COMMIT_MSG` env var to the engine script.

**Primary actions:**

- **Dry-run (safe)** — scans all repos; never commits or pushes. Safe to run any time.
- **Sync now** — commits and pushes all clean repos after the leak-gate. Disabled
  until gitleaks is found on disk, with an install hint shown in a banner.
  Shows a **diff preview** (git status --short for each repo) before you confirm.

**Secondary actions:**

- **Create GitHub Repo…** — lists local projects under `~/Documents/lab/active/`
  that don't have a GitHub remote yet, lets you pick visibility, adds the repo to
  the config list, then runs the `--create-remote` flow. Shows the new repo's URL
  on success.
- **Schedule…** — configure a background `launchd` job: "run every" (15 min /
  30 min / 1 h / 6 h / 12 h / 24 h) or "run daily at" a specific time. Shows the
  current schedule; lets you update or disable it.
- **Logs** — reveals the log folder in Finder.
- **Docs** — renders this README in an in-app viewer.
- **Tooltips** — toggles explanatory tooltips on every control.
- **Edit list** — opens `autosync_repos.txt` in your default editor.

**Output pane:**

Live log output from the engine script, with ANSI colour codes stripped for
readability. After a blocked run, the output pane appends a **leak report**
listing the file, rule, and fingerprint that triggered the gate for each blocked
repo, so you know exactly what to fix without opening the log file.

**Status bar:**

- **Last sync** — timestamp from the engine's own state file (accurate whether
  the last run was manual or scheduled).
- **Next sync** — computed from the active schedule, or "not scheduled".

**macOS notifications:**

After every real sync the app fires a macOS notification (`display notification`)
with a summary of how many repos were synced, blocked, and skipped. The
notification appears in Notification Centre even if the app window is hidden.

### Tray icon and background behaviour

The app lives in the macOS menu bar as a coloured dot:
- **Green** — last run completed with no blocks or errors.
- **Red** — at least one repo was blocked or errored.
- **Grey** — no real run has completed yet.

Closing the main window does **not** quit the app — it hides to the tray so
scheduled syncs keep running in the background. To reopen: click the tray dot or
the Dock icon. To quit fully: choose **Quit** from the tray menu.

The tray menu also has quick **Dry-run** and **Sync now** actions so you don't
need to open the window at all.

The app is **single-instance**: launching a second copy raises the existing
window instead of opening a duplicate.

### Running from source

```bash
uv venv .venv && source .venv/bin/activate
uv pip install -r requirements.txt
python -m app.main
```

### Building the standalone `.app`

```bash
./build_app.sh
```

Installs to `/Applications/git_autosync.app`. The script deletes `build/` and
`dist/` after installing so Spotlight never indexes a second copy.

The app is ad-hoc signed (`codesign --force --deep -s -`), so the first launch
needs right-click → Open (no Apple Developer ID / notarization yet).

### Notes

- Config, logs, and last-sync state live in
  `~/Library/Application Support/git_autosync/` (the packaged bundle is
  read-only), seeded from `autosync_repos.txt` on first run.
- The packaged app resolves `gitleaks` / `git` / `gh` explicitly (checking
  `/opt/homebrew/bin`, `/usr/local/bin`, then `PATH`) because Finder-launched
  apps don't inherit your shell's PATH.
- The app icon (`packaging/icon.icns`) is generated by `packaging/make_icon.py`.
  Regenerate it with:
  ```bash
  python packaging/make_icon.py && cd packaging && iconutil -c icns icon.iconset -o icon.icns && rm -rf icon.iconset
  ```

## Git identity

Commits use a pseudonymous identity, not a real name/email — `git config --global
user.name / user.email` should already be set to the `Netrunner3000` GitHub noreply
identity. Don't hardcode a real name/email anywhere in this project.
