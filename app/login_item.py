"""Manage autostart-at-login via a LaunchAgent plist (separate from the sync schedule).

Writes ~/Library/LaunchAgents/com.netrunner3000.git-autosync-login.plist
with RunAtLoad=true and no StartInterval, so the GUI starts hidden in the
menu bar on every login. Uses --background so no window appears at startup.
"""
import plistlib
import subprocess
from pathlib import Path

from . import paths

_LABEL = "com.wwds-dev.git-autosync-login"
_LEGACY_LABELS = ("com.netrunner3000.git-autosync-login",)
_APP   = "/Applications/git_autosync.app/Contents/MacOS/git_autosync"


def _plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{_LABEL}.plist"


def migrate_legacy() -> list[str]:
    """Drop a login item left behind under the pre-rename label."""
    done = []
    for label in _LEGACY_LABELS:
        p = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"
        if p.exists():
            subprocess.run(["launchctl", "unload", "-w", str(p)], capture_output=True)
            p.unlink(missing_ok=True)
            done.append(label)
    return done


def is_enabled() -> bool:
    return _plist_path().exists()


def enable() -> None:
    plist = {
        "Label": _LABEL,
        "ProgramArguments": [_APP, "--background"],
        "RunAtLoad": True,
        "KeepAlive": False,
        "StandardOutPath": "/dev/null",
        "StandardErrorPath": "/dev/null",
    }
    path = _plist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        plistlib.dump(plist, f)
    subprocess.run(["launchctl", "load", "-w", str(path)],
                   capture_output=True)


def disable() -> None:
    path = _plist_path()
    if path.exists():
        subprocess.run(["launchctl", "unload", "-w", str(path)],
                       capture_output=True)
        path.unlink(missing_ok=True)
