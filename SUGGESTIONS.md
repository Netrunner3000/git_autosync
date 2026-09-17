# git_autosync — Suggestions

Status: `IDEA` · `CONSIDERING` · `PLANNED` · `DONE` · `REJECTED`

---

| # | Suggestion | Category | Effort | Status |
|---|---|---|---|---|
| 3 | Per-repo commit-message templates | feature | M | CONSIDERING |
| 4 | GUI dry run — show the exact diff that would be pushed | feature | M | CONSIDERING |
| 5 | Parallel repo scanning; gitleaks dominates runtime | performance | M | IDEA |
| 6 | Notification on a blocked repo, rather than a line in the log | feature | S | IDEA |
| 7 | A "publish this project" wizard wrapping `--create-remote`, `.gitignore` check and first push | feature | L | IDEA |

## Done

| Suggestion | When |
|---|---|
| Fail closed (and say so loudly) when `gitleaks` is missing | Aug 2026 |
| Last-sync state surfaced in the GUI | Aug 2026 |
| Privacy button shows live repo visibility (🔒/🌐), fetched via `gh api` on a background timer | Aug 2026 |
| Fix leak… button turns red while a repo is currently blocked | Aug 2026 |
| `--background` launch flag — starts hidden, or tells an already-running instance to stay hidden, without the "already running" alert | Aug 2026 |
| launchd scheduling — fixed interval and daily-at-a-time | Aug 2026 |
| Tray icon and background behaviour | Aug 2026 |
| `--create-remote` publishing flow | Aug 2026 |
| User-writable config/log location, `AUTOSYNC_LOG_DIR` | Aug 2026 |

## Rejected

| Suggestion | Why |
|---|---|
| Developer ID notarisation | $99/yr for a personal single-machine tool |
