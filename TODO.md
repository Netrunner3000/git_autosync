# git_autosync — TODO

> **Legend** — priority `P0` critical · `P1` high · `P2` normal · `P3` low
> categories `security` `bug` `feature` `performance` `design` `docs` `testing` `infra` `research`
> owner `@me` (needs you — accounts, keys, money, judgement) · `@ai` (Claude can do this)

---

## v2 — current

- [ ] `P0` `security` `@me` **Rotate any credential that was ever committed.** Repos with secrets in history stay out of `autosync_repos.txt`; publishing one requires history cleanup first, and the credential should be rotated regardless of what GitHub sees.
- [ ] `P1` `security` `@me` Confirm `gitleaks` is installed (`brew install gitleaks`) — without it the leak gate is a stub, and the whole safety argument for autosync rests on it
- [x] `P1` `testing` `@ai` Assert the app fails closed when `gitleaks` is missing, rather than syncing unscanned
- [x] `P2` `bug` `@ai` Repos with no `origin` should be skipped with a clear status, not treated as a failure
- [x] `P2` `feature` `@ai` Surface the last-sync state file in the GUI — it exists on disk and nothing shows it
- [x] `P3` `docs` `@ai` HANDOVER.md is the original spec and the README is the source of truth; add a one-line note at the top of HANDOVER saying so
- [x] `P1` `feature` `@ai` launchd scheduling (fixed-interval and daily-at-a-time) via the *Schedule sync…* dialog
- [x] `P2` `infra` `@ai` User-writable config and log location plus the `AUTOSYNC_LOG_DIR` knob
- [x] `P2` `feature` `@ai` `--create-remote` for publishing a new project to GitHub

## v3 — later

- [ ] `P2` `feature` `@ai` Per-repo commit-message templates rather than one global custom message
- [ ] `P3` `feature` `@ai` Dry-run mode in the GUI that shows exactly what would be committed and pushed
- [ ] `P3` `performance` `@ai` Parallel scanning across repos — currently serial, and gitleaks dominates the runtime

## Resolved decisions

- Install destination: `/Applications`
- Code signing: ad-hoc only. No Developer ID — not worth $99/yr for a personal single-machine tool.
