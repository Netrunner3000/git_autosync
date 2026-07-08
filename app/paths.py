"""Path resolution for the git_autosync GUI.

Finder-launched .app bundles get a minimal PATH (no /opt/homebrew/bin), and a
PyInstaller bundle is read-only, so every path used at runtime has to be
resolved explicitly rather than relied on from the environment.
"""
import os
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Extra directories to search for CLI tools, beyond whatever PATH the app was
# launched with (Finder-launched apps don't inherit the shell's PATH).
EXTRA_BIN_DIRS = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"]


def bundle_root() -> Path:
    """Directory containing bundled data files (engine script, etc.)."""
    return Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))


def engine_script() -> Path:
    return bundle_root() / "git_autosync.sh"


def readme_path() -> Path:
    return bundle_root() / "README.md"


def child_env_path() -> str:
    """A PATH string that includes the usual Homebrew/system locations."""
    current = os.environ.get("PATH", "")
    parts = [p for p in current.split(":") if p]
    for d in EXTRA_BIN_DIRS:
        if d not in parts:
            parts.append(d)
    return ":".join(parts)


def find_binary(name: str) -> str | None:
    """Resolve a binary by name, checking EXTRA_BIN_DIRS then PATH."""
    for d in EXTRA_BIN_DIRS:
        candidate = Path(d) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    found = shutil.which(name)
    return found


def find_gitleaks() -> str | None:
    return find_binary("gitleaks")


def find_git() -> str | None:
    return find_binary("git")


def find_gh() -> str | None:
    return find_binary("gh")


def lab_active_dir() -> Path:
    return Path(os.environ.get("LAB_ACTIVE", str(Path.home() / "Documents" / "lab" / "active")))


def repos_without_remote() -> list[Path]:
    """Git repos under lab_active_dir() that have no 'origin' remote configured —
    candidates for the "Create GitHub repo" flow."""
    base = lab_active_dir()
    if not base.is_dir():
        return []
    candidates = []
    for child in sorted(base.iterdir()):
        if not (child / ".git").is_dir():
            continue
        git = find_git() or "git"
        result = subprocess_run([git, "-C", str(child), "remote", "get-url", "origin"])
        if result != 0:
            candidates.append(child)
    return candidates


def subprocess_run(cmd: list[str]) -> int:
    import subprocess

    return subprocess.run(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ).returncode


def app_support_dir() -> Path:
    d = Path.home() / "Library" / "Application Support" / "git_autosync"
    d.mkdir(parents=True, exist_ok=True)
    return d


def user_log_dir() -> Path:
    d = app_support_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def last_sync_path() -> Path:
    return app_support_dir() / "last_sync.txt"


def read_last_sync() -> str | None:
    """Written by git_autosync.sh itself (AUTOSYNC_STATE_DIR) after any real
    run, whether triggered by the GUI or the scheduled background job."""
    p = last_sync_path()
    return p.read_text().strip() if p.exists() else None


def last_status_path() -> Path:
    return app_support_dir() / "last_status.txt"


def read_last_status() -> str | None:
    """'ok' or 'attention', written alongside last_sync.txt. None if no real
    run has completed yet."""
    p = last_status_path()
    return p.read_text().strip() if p.exists() else None


def user_config_path() -> Path:
    """Writable repo-list location, seeded from the bundled default on first run."""
    cfg = app_support_dir() / "autosync_repos.txt"
    if not cfg.exists():
        seed = bundle_root() / "autosync_repos.txt"
        if seed.exists():
            cfg.write_text(seed.read_text())
        else:
            cfg.write_text(
                "# autosync_repos.txt — one repo per line, bare name resolves\n"
                "# under ~/Documents/lab/active/. Lines starting with # are ignored.\n"
            )
    return cfg
