"""Per-repo last-synced tracking, for the "stale repo" indicator in the GUI.

git_autosync.sh only writes one global last_sync.txt (last time it ran for
real, regardless of outcome); this tracks the last time each *individual*
repo actually showed SYNCED, so a repo that's been silently skipped/blocked
for days can be flagged even if other repos are syncing fine.
"""
import json
from datetime import datetime, timedelta

from . import paths

STALE_AFTER_DAYS = 3


def _state_path():
    return paths.app_support_dir() / "repo_last_synced.json"


def _lookup(data: dict, repo_name: str) -> str | None:
    """Timestamp for a repo, tolerating the pre-2026-09 key format.

    The engine used to report a repo by its bare directory name while the GUI
    keyed rows by config entry, so every subpath repo read back as "never".
    The engine now reports the entry; fall back to the basename so history
    written under the old scheme still counts.
    """
    stamp = data.get(repo_name)
    if stamp:
        return stamp
    base = repo_name.rstrip("/").split("/")[-1]
    return data.get(base) if base != repo_name else None


def read_all() -> dict:
    p = _state_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def record_synced(repo_names: list[str], when: datetime | None = None) -> None:
    if not repo_names:
        return
    when = when or datetime.now()
    data = read_all()
    stamp = when.strftime("%Y-%m-%d %H:%M:%S")
    for name in repo_names:
        data[name] = stamp
    _state_path().write_text(json.dumps(data, indent=2))


def days_since_synced(repo_name: str) -> int | None:
    """None if never recorded as synced."""
    stamp = _lookup(read_all(), repo_name)
    if not stamp:
        return None
    try:
        last = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return (datetime.now() - last).days


def humanize(when) -> str | None:
    """'just now' / '5m ago' / '2h ago' / '3d ago' from a datetime."""
    if when is None:
        return None
    total = int((datetime.now() - when).total_seconds())
    if total < 90:
        return "just now"
    if total < 3600:
        return f"{total // 60}m ago"
    if total < 86400:
        return f"{total // 3600}h ago"
    return f"{total // 86400}d ago"


def time_since_synced(repo_name: str) -> str | None:
    """Human-readable 'just now / 5m ago / 2h ago / 3d ago'. None if never synced."""
    stamp = _lookup(read_all(), repo_name)
    if not stamp:
        return None
    try:
        last = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    delta = datetime.now() - last
    total_seconds = int(delta.total_seconds())
    if total_seconds < 90:
        return "just now"
    if total_seconds < 3600:
        return f"{total_seconds // 60}m ago"
    if total_seconds < 86400:
        return f"{total_seconds // 3600}h ago"
    return f"{delta.days}d ago"


def is_stale(repo_name: str) -> bool:
    days = days_since_synced(repo_name)
    return days is None or days >= STALE_AFTER_DAYS
