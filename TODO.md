# git_autosync — TODO

> **Legend** — priority `P0` critical · `P1` high · `P2` normal · `P3` low
> categories `security` `bug` `feature` `performance` `design` `docs` `testing` `infra` `research`
> owner `@me` (needs you — accounts, keys, money, judgement) · `@ai` (Claude can do this)

---

## v2 — current

- [x] `P1` `feature` `@ai` **push-only mode.** A sweep in a repo someone is working in rolls unrelated half-finished changes into one `autosync: <timestamp>` commit — `imprint` collected three on consecutive nights, one burying most of a docs rewrite. A config line may now carry `push-only`: push existing commits, never stage or commit, never publish an untracked branch. History scan still runs; staged scan skipped because nothing is staged. `imprint` and `imprint/vidforge` are set to it in the live config.
- [x] `P2` `testing` `@ai` **The engine had no tests.** Uncomfortable for the one tool whose job is writing to every other repo. `tests/test_push_only.py` drives the real shell script against throwaway repos and a throwaway remote. Two self-inflicted bugs it caught: the first version *skipped* when its fixture was misconfigured, so seven useless skips read as success; and the no-upstream branch in the push block was unreachable, because `ahead` is only counted when an upstream exists — the protection worked by accident and logged "nothing to push" while sitting on commits.
- [ ] `P0` `security` `@me` **Rotate any credential that was ever committed.** Repos with secrets in history stay out of `autosync_repos.txt`; publishing one requires history cleanup first, and the credential should be rotated regardless of what GitHub sees.
- [ ] `P1` `infra` `@me` **Coverage has fallen far behind the repo count.** The Sep 2026
  reorg left 21 repos under `active/`; `autosync_repos.txt` lists 5. Uncovered:
  `lab_hub`, `imprint`, `imprint/vidforge`, `sentinel_fork`, `sentinel_fork/bug_spray`,
  `sonar`, `sonar/sonar/macro`, `sonar/sonar/playmaker`, `toolbox`,
  `toolbox/unblock_tracker`, `bazaar`, and the five `sentinel_fork/agents/*` repos.
  Consequences already visible: **`imprint` is 30 commits ahead of its remote**,
  `sentinel_fork/vpn_agent` 1, and `bug_spray` has uncommitted work.
- [ ] `P1` `infra` `@me` **Nine repos have no remote at all**, so nothing is backing them
  up but the nightly Drive rsync: `bazaar`, `sentinel_fork/bug_spray`, `toolbox`,
  `sonar/sonar/macro`, `sonar/sonar/playmaker`, and the five `sentinel_fork/agents/*`.
  A repo without a remote cannot be autosynced — `--create-remote` is the way in.
- [ ] `P2` `research` `@ai` Nested repos need a coverage rule. `toolbox/` is a repo that
  *contains* three repos, and `sentinel_fork/` contains three more. Decide whether the
  parent, the children, or both belong in `autosync_repos.txt`, and make sure the
  parent's `.gitignore` keeps `git add -A` from turning a child into an embedded gitlink.
- [ ] `P1` `security` `@me` Confirm `gitleaks` is installed (`brew install gitleaks`) — without it the leak gate is a stub, and the whole safety argument for autosync rests on it
- [x] `P1` `testing` `@ai` Assert the app fails closed when `gitleaks` is missing, rather than syncing unscanned
- [x] `P2` `bug` `@ai` Repos with no `origin` should be skipped with a clear status, not treated as a failure
- [x] `P2` `feature` `@ai` Surface the last-sync state file in the GUI — it exists on disk and nothing shows it
- [x] `P3` `docs` `@ai` HANDOVER.md is the original spec and the README is the source of truth; add a one-line note at the top of HANDOVER saying so
- [x] `P1` `feature` `@ai` launchd scheduling (fixed-interval and daily-at-a-time) via the *Schedule sync…* dialog
- [x] `P2` `infra` `@ai` User-writable config and log location plus the `AUTOSYNC_LOG_DIR` knob
- [x] `P2` `feature` `@ai` `--create-remote` for publishing a new project to GitHub
- [x] `P1` `feature` `@ai` **Find repos… reconciles the effective config with repositories on disk.** The preview identifies additions and missing paths; missing rows stay disabled and the main view warns when the list has drifted.
- [x] `P1` `bug` `@ai` **Nested repository status is keyed by config entry.** Repositories with the same leaf-name context no longer lose their per-entry last-sync state or display “never” incorrectly.
- [x] `P2` `design` `@ai` **Repository rows are readable at a glance.** Column headers align the controls, the repository name leads, the containing folders trail in muted text, and the None button no longer clips.
- [x] `P2` `maintenance` `@ai` Follow SONAR's `sports` → `playmaker` repository rename in the tracked-project list.

## v3 — later

- [ ] `P2` `feature` `@ai` Per-repo commit-message templates rather than one global custom message
- [ ] `P3` `feature` `@ai` Dry-run mode in the GUI that shows exactly what would be committed and pushed
- [ ] `P3` `performance` `@ai` Parallel scanning across repos — currently serial, and gitleaks dominates the runtime

## Resolved decisions

- Install destination: `/Applications`
- Code signing: ad-hoc only. No Developer ID — not worth $99/yr for a personal single-machine tool.
