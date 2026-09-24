"""Installs/removes a launchd LaunchAgent that runs the engine on a schedule,
so autosync keeps working in the background even when the GUI isn't open —
mirrors the pattern used by _Admin/backup's nightly job.

Two scheduling modes, matching what launchd itself supports:
  - "interval": run every N seconds (StartInterval).
  - "calendar": run once a day at a fixed time (StartCalendarInterval).
"""
import plistlib
import subprocess
from pathlib import Path

from . import paths

LABEL = "com.wwds-dev.git-autosync"
# The account was renamed from Netrunner3000; agents installed under the old
# label keep running until they are unloaded, so migrate rather than orphan.
LEGACY_LABELS = ("com.netrunner3000.git-autosync",)


def plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def _legacy_plist_paths():
    d = Path.home() / "Library" / "LaunchAgents"
    return [d / f"{label}.plist" for label in LEGACY_LABELS]


def _parse_schedule(path: Path) -> dict | None:
    """Read a schedule out of a specific plist, whatever its label."""
    if not path.exists():
        return None
    try:
        with path.open("rb") as f:
            data = plistlib.load(f)
    except Exception:
        return None
    run_at_load = bool(data.get("RunAtLoad", False))
    if "StartInterval" in data:
        return {"mode": "interval",
                "interval_seconds": int(data["StartInterval"]),
                "run_at_load": run_at_load}
    cal = data.get("StartCalendarInterval")
    if isinstance(cal, dict):
        return {"mode": "calendar", "hour": int(cal.get("Hour", 0)),
                "minute": int(cal.get("Minute", 0)), "run_at_load": run_at_load}
    return None


def migrate_legacy() -> tuple[list[str], dict | None]:
    """Unload and remove agents left under the old label.

    Returns (labels_removed, schedule_found). The schedule has to be read from
    the legacy plist before it is deleted — get_schedule() looks at the *new*
    label's path, which does not exist yet, so relying on it silently loses the
    user's schedule.
    """
    done, schedule = [], None
    for p in _legacy_plist_paths():
        if not p.exists():
            continue
        schedule = schedule or _parse_schedule(p)
        subprocess.run(["launchctl", "unload", "-w", str(p)], capture_output=True)
        p.unlink(missing_ok=True)
        done.append(p.stem)
    return done, schedule


def is_installed() -> bool:
    return plist_path().exists()


def get_schedule() -> dict | None:
    """Returns the current schedule config, or None if not installed.

    {"mode": "interval", "interval_seconds": int, "run_at_load": bool}
    {"mode": "calendar", "hour": int, "minute": int, "run_at_load": bool}
    """
    p = plist_path()
    if not p.exists():
        return None
    try:
        with p.open("rb") as f:
            data = plistlib.load(f)
    except Exception:
        return None

    run_at_load = bool(data.get("RunAtLoad", False))
    if "StartInterval" in data:
        return {"mode": "interval", "interval_seconds": data["StartInterval"], "run_at_load": run_at_load}
    cal = data.get("StartCalendarInterval")
    if isinstance(cal, dict):
        return {
            "mode": "calendar",
            "hour": cal.get("Hour", 0),
            "minute": cal.get("Minute", 0),
            "run_at_load": run_at_load,
        }
    return None


def _base_plist(config_path: Path, run_at_load: bool) -> dict:
    bash = paths.find_binary("bash") or "/bin/bash"
    log_dir = paths.user_log_dir()
    return {
        "Label": LABEL,
        "ProgramArguments": [bash, str(paths.engine_script())],
        "EnvironmentVariables": {
            "PATH": paths.child_env_path(),
            "AUTOSYNC_CONFIG": str(config_path),
            "AUTOSYNC_LOG_DIR": str(log_dir),
            "AUTOSYNC_STATE_DIR": str(paths.app_support_dir()),
            "GITLEAKS_CMD": paths.find_gitleaks() or "gitleaks",
            "GH_CMD": paths.find_gh() or "gh",
        },
        "RunAtLoad": run_at_load,
        "StandardOutPath": str(log_dir / "launchd.log"),
        "StandardErrorPath": str(log_dir / "launchd.log"),
    }


def install_interval(interval_seconds: int, config_path: Path, run_at_load: bool = False) -> None:
    plist = _base_plist(config_path, run_at_load)
    plist["StartInterval"] = interval_seconds
    _write_and_load(plist)


def install_calendar(hour: int, minute: int, config_path: Path, run_at_load: bool = False) -> None:
    plist = _base_plist(config_path, run_at_load)
    plist["StartCalendarInterval"] = {"Hour": hour, "Minute": minute}
    _write_and_load(plist)


def _write_and_load(plist: dict) -> None:
    path = plist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        plistlib.dump(plist, f)

    subprocess.run(["launchctl", "unload", str(path)], capture_output=True)
    subprocess.run(["launchctl", "load", "-w", str(path)], capture_output=True, check=True)


def uninstall() -> None:
    path = plist_path()
    if path.exists():
        subprocess.run(["launchctl", "unload", str(path)], capture_output=True)
        path.unlink()
