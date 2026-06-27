# Handover — build `git_autosync` as an executable macOS app

**For:** Claude Code, working in `~/Documents/lab`
**Repo:** `~/Documents/lab/active/git_autosync` (its own git repo)
**Goal:** Add a double-clickable **PySide6 GUI macOS `.app`** to this repo, packaged with PyInstaller. The GUI must **reuse the existing, tested bash core** (`git_autosync.sh` at the repo root) — do not reimplement the leak-gate logic.
**Author identity for commits:** `Andreas Seel` / `andreas.seel@live.de`

---

## 1. TL;DR

This repo already contains a working, tested CLI: `git_autosync.sh`. It commits & pushes selected repos, but only after **gitleaks** clears each one (no clean scan → no push). Build a desktop GUI around it in `app/`: a window that lists the repos, has **Run** / **Dry-run** buttons, and shows live scan/sync results and the log. Ship it as an ad-hoc-signed `.app`.

The GUI is a thin front-end. `git_autosync.sh` stays the single source of truth for the safety gate.

---

## 2. Background — what already exists

The user (new to GitHub) published 5 of 7 `/lab/active` projects to GitHub as public repos and built this auto-sync tool. Relevant facts:

- **5 repos are targets for autosync:** `backup_manager`, `convert_epub`, `image_tools`, `sentinel_ai`, `vpn_agent`.
- **Some repos are excluded** because they still have secrets committed in their history. They must NOT be published until the secrets are removed, the history is cleaned, and the affected credentials are rotated. The autosync history-scan blocks them by design — keep them out of `autosync_repos.txt`.
- A publish helper exists: `~/Documents/lab/setup_github.command` (creates the GitHub repos via `gh` and pushes). The user may or may not have run it yet — **do not assume the 5 repos already have an `origin` remote.** Tolerate "no remote → skip".

### The engine in this repo (reuse it — don't fork it)

| File (repo root) | Purpose |
|---|---|
| `git_autosync.sh` | The engine. Stages → scans (gitleaks) → commits → pushes, per repo. **Tested.** |
| `autosync_repos.txt` | Source-of-truth list of repos to sync (bare name resolves under `active/`). |
| `git_autosync.command` | Double-click launcher (Terminal). |
| `README.md` | Usage docs. |
| `logs/` | Dated run logs (`autosync_YYYYMMDD.log`). |

> Note: this tool used to live at `_Admin/git_autosync/`. It was moved here so the engine and the GUI app form one project/repo. There should be **no copy left in `_Admin/`** — if you find one, the version in this repo is canonical.

**`git_autosync.sh` contract (rely on this — it's tested):**

- Flags: `--dry-run` (read-only: scan + report, never commit/push), `--repo NAME` (single repo), `--help`.
- Env overrides (use these from the GUI):
  - `AUTOSYNC_CONFIG` — path to the repo-list file.
  - `LAB_ACTIVE` — base dir for bare repo names (default `$HOME/Documents/lab/active`).
  - `GITLEAKS_CMD` — gitleaks binary (default `gitleaks`).
- **Exit code:** `0` = all good / nothing to do; **non-zero** = at least one repo was BLOCKED or errored.
- **Per-repo outcomes** it prints (parse these for status badges): `SYNCED`, `BLOCKED` (secret in changes or history), `SKIP` (no git repo / no remote), `ERROR`, dry-run `OK`. A `SUMMARY:` block ends the run with one line per repo plus a counts line: `synced=… blocked=… skipped=… errors=… noop=…`.
- Logs go to `logs/autosync_YYYYMMDD.log`; **gitleaks output is redacted** (`--redact`) so secret values never hit disk.

**Gate is verified.** Tested against throwaway repos with a faithful gitleaks stub + local bare remotes: clean repo synced; a secret in a *pending change* was blocked before commit; a secret in *history* was blocked before push; `--dry-run` made zero changes. Preserve this behavior.

---

## 3. Conventions to honor (from `~/Documents/lab/CLAUDE.md`)

- **Each active project is its own git repo** with the standard `.gitignore` (already present here).
- **No hardcoded `/Users/...` paths in code.** Use `PROJECT_ROOT = Path(__file__).resolve().parent` (or `parents[1]`); external dirs via env vars or `$HOME`.
- **Environments with `uv`** — venvs disposable, kept out of git. (See `_Admin/UV_SETUP.md`.)
- **GUI apps are PySide6.** Match the style of `active/backup_manager/` (PySide6 "Backup Control Center", has a `build_app.sh`) and `active/sentinel_ai/`.
- Don't commit `.env` or `venv/`.

---

## 4. Target structure (add to THIS repo)

```
active/git_autosync/
  git_autosync.sh         # engine — already here, canonical, tested
  autosync_repos.txt
  git_autosync.command
  logs/
  README.md
  HANDOVER.md
  requirements.txt        # NEW: PySide6 (+ pyinstaller as dev dep)
  app/                    # NEW: the GUI
    __init__.py
    main.py               # entry point (QApplication)
    ui_main.py            # main window: repo list, Run/Dry-run, log pane
    runner.py             # wraps git_autosync.sh via QProcess; parses output
    config.py             # read/write autosync_repos.txt
    paths.py              # locate engine script, gitleaks, git (see gotchas §6)
  packaging/              # NEW
    git_autosync.spec     # PyInstaller spec (bundles the engine + icon)
    icon.icns
```

The engine stays at the repo root and is the **single source of truth** (this resolves the old "two copies" question — there is one copy, here). In dev, the GUI shells out to `../git_autosync.sh` relative to `app/`; in the packaged app, PyInstaller bundles the script and the GUI resolves it under `sys._MEIPASS` (see §6).

---

## 5. Functional spec (the GUI)

Minimum viable window:

1. **Repo list** — checkbox list populated from `autosync_repos.txt`. After a run each row shows a status badge: ✅ Synced · ⛔ Blocked · ⏭ Skipped · ⚠️ Error · ➖ No-op. Repos excluded for containing committed secrets aren't in the config and shouldn't appear unless the user adds them.
2. **Buttons:**
   - **Dry-run** → `git_autosync.sh --dry-run` (read-only). Make this the visually "safe" default.
   - **Sync now** → `git_autosync.sh` (real commit+push). Consider a confirm dialog.
   - **Edit repo list** → edit `autosync_repos.txt`.
   - **Open logs** → reveal `logs/` or tail today's log in-pane.
3. **Live output pane** — stream stdout/stderr via `QProcess` + `readyReadStandardOutput`. Never block the UI thread.
4. **Summary line** — after a run show `synced/blocked/skipped/errors`. If exit code ≠ 0, banner it (red: "Some repos were blocked — see log").
5. **First-run / preflight** — if `gitleaks` isn't found, show "Install the scanner: `brew install gitleaks`" with a copy button, and **refuse to run a real sync** (never bypass the gate).

Backlog (note, don't build yet): per-repo dry-run, "last synced" timestamps, menu-bar companion, launchd scheduling toggle mirroring `_Admin/backup/`.

---

## 6. Critical implementation gotchas (do not skip)

- **PATH is minimal for Finder-launched `.app`s.** Apps launched from Finder/Dock do **not** inherit your shell PATH, so `gitleaks` and even `git` at `/opt/homebrew/bin` won't be found. In `runner.py`, build the child env with `PATH` explicitly including `/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin`, and/or resolve `gitleaks` and `git` to absolute paths (check `/opt/homebrew/bin`, `/usr/local/bin`, then `shutil.which`). Pass the resolved gitleaks path via `GITLEAKS_CMD`. **This is the most likely thing to break in the packaged app — test it from Finder, not just the terminal.**
- **Locate the bundled engine robustly.** Under PyInstaller the bundle is read-only and files live under `sys._MEIPASS`. Resolve the script relative to `getattr(sys, "_MEIPASS", PROJECT_ROOT)`. Invoke via `bash <script>` (don't rely on the exec bit surviving packaging).
- **Config & logs must be writable.** The bundle is read-only. Point `AUTOSYNC_CONFIG` and logs at a user-writable location, e.g. `~/Library/Application Support/git_autosync/` (create on first run; seed the config from the repo's `autosync_repos.txt`). The engine currently writes logs next to itself — add an `AUTOSYNC_LOG_DIR` env knob to `git_autosync.sh` and have the GUI set it, rather than hardcoding.
- **Don't block the UI.** Use `QProcess` (async), not `subprocess.run` on the main thread.
- **Gatekeeper.** An unsigned `.app` triggers "unidentified developer". Ad-hoc sign (`codesign --force --deep -s - git_autosync.app`) and document the right-click→Open first launch, or note that proper notarization needs an Apple Developer ID (out of scope unless the user has one).
- **Apple Silicon.** Target arm64 (user is on M2 / macOS Tahoe 26); build with the arm64 Python from uv.

---

## 7. Packaging

- Dev env via uv; `requirements.txt`: `PySide6`. Dev-only: `pyinstaller`.
- `pyinstaller packaging/git_autosync.spec` →  `dist/git_autosync.app`.
- The spec must include `git_autosync.sh` (and icon) as `datas`, and set `BUNDLE(... name='git_autosync.app', icon='packaging/icon.icns')`.
- Mirror `active/backup_manager/build_app.sh` if it already does PyInstaller packaging.
- Verify the `.app` launches from Finder and a dry-run works **with gitleaks resolved via the bundled PATH logic**.

---

## 8. Testing & acceptance criteria

Reproduce the CLI gate at the GUI layer. Definition of done:

1. App launches from Finder as `git_autosync.app` (not just from terminal).
2. With **gitleaks missing**, real sync is disabled and the install hint shows.
3. **Dry-run** on the 5 repos runs read-only and changes nothing (no new commits, remote unchanged).
4. A repo with a **planted secret in a pending change** shows ⛔ Blocked and is NOT committed/pushed (reuse the throwaway-repo + local-bare-remote + gitleaks-stub approach, or real gitleaks after `brew install gitleaks`).
5. A repo with a **secret in history** is ⛔ Blocked before push.
6. A **clean** repo shows ✅ Synced and the commit reaches the remote.
7. Non-zero exit produces a visible "blocked/error" banner.
8. No secret value is ever written to logs or shown unredacted in the UI.
9. The packaged app's `PATH`/gitleaks resolution works **when launched from Finder** (the #1 packaging risk).

Add a pytest for `runner.py`'s output parser (feed sample stdout, assert it extracts per-repo statuses + counts).

---

## 9. Known current state / environment

- macOS Tahoe 26, Apple Silicon (M2). Homebrew at `/opt/homebrew`. Python via uv. GUI = PySide6.
- **gitleaks is not installed yet** — `brew install gitleaks` required before real scans. Until then, test with the stub approach.
- The 5 target repos have local `.git` history; they may not yet have a GitHub `origin` (depends on whether `setup_github.command` was run). Handle "no remote → skip".
- This repo (`active/git_autosync`) may not be git-initialized yet at the moment you read this — if `git status` errors, run `git init`, then commit as `Andreas Seel`.

---

## 10. Security reminders (carry forward)

- Repos that hold secrets committed in history must stay out of `autosync_repos.txt`. Any such credentials should be rotated regardless of GitHub, and publishing requires history cleanup first.
- The gate is a safety net, not a license to hardcode secrets. Keep env-vars + `.gitignore` as the first line of defense.

---

## 11. Suggested order of work

1. Ensure this repo is git-initialized; add `requirements.txt` and a uv env.
2. Build `runner.py` (QProcess wrapper + output parser) and prove it against the CLI before adding UI.
3. Add `paths.py` PATH/gitleaks resolution (§6) — get this right early.
4. Build the window (`ui_main.py`): repo list, buttons, live log, status badges.
5. Add the user-writable config/log location; add the `AUTOSYNC_LOG_DIR` knob to `git_autosync.sh`.
6. Package with PyInstaller; **test from Finder**; fix PATH issues.
7. Run the acceptance checklist (§8). Commit as `Andreas Seel`.

---

## 12. Open decisions to confirm with the user

- App install destination: `/Applications` vs `~/Applications` vs run-from-`dist`.
- Whether to also add scheduling (launchd nightly) now or leave as backlog.
- Code signing: ad-hoc (right-click→Open) vs the user has a Developer ID for notarization.
