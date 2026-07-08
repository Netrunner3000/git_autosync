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
    data = read_all()
    stamp = data.get(repo_name)
    if not stamp:
        return None
    try:
        last = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return (datetime.now() - last).days


def is_stale(repo_name: str) -> bool:
    days = days_since_synced(repo_name)
    return days is None or days >= STALE_AFTER_DAYS
