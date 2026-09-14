"""Read/write the autosync repo list.

A line is a repo, optionally followed by mode flags:

    backup_manager
    imprint            push-only

`push-only` means: push commits that already exist, and never `git add -A` and
commit the working tree on the user's behalf. That distinction matters for any
repo a person or an agent is actively working in — a sweep there produces a
commit titled `autosync: <timestamp>` containing several unrelated
half-finished changes, which is worse than no backup of them, because it looks
like history.

`read_repos()` returns bare entries, because that is what the GUI displays and
keys its rows by. Modes are read separately with `read_modes()` and preserved
across `write_repos()` — a round-trip through the GUI must not silently drop a
flag the user set, which is the failure mode this split exists to avoid.
"""
from pathlib import Path

#: Recognised mode flags. Anything else on the line is ignored rather than
#: treated as part of the repo path, so a typo degrades to the default
#: behaviour instead of pointing the engine at a directory that cannot exist.
MODES = ("push-only",)


def _split(line: str) -> tuple[str, tuple[str, ...]]:
    """('imprint  push-only') -> ('imprint', ('push-only',))"""
    line = line.split("#", 1)[0].strip()
    if not line:
        return "", ()
    parts = line.split()
    return parts[0], tuple(p for p in parts[1:] if p in MODES)


def read_repos(config_path: Path) -> list[str]:
    """Repo entries, without their mode flags."""
    repos = []
    for line in config_path.read_text().splitlines():
        entry, _modes = _split(line)
        if entry:
            repos.append(entry)
    return repos


def read_modes(config_path: Path) -> dict[str, tuple[str, ...]]:
    """entry -> its mode flags. Entries with no flags are omitted."""
    modes = {}
    for line in config_path.read_text().splitlines():
        entry, entry_modes = _split(line)
        if entry and entry_modes:
            modes[entry] = entry_modes
    return modes


def is_push_only(config_path: Path, entry: str) -> bool:
    return "push-only" in read_modes(config_path).get(entry, ())


def write_repos(config_path: Path, repos: list[str],
                modes: dict[str, tuple[str, ...]] | None = None) -> None:
    """Write the list, keeping each entry's flags.

    Flags default to whatever the file already holds, so the GUI — which only
    ever passes bare names — cannot drop one by saving.
    """
    if modes is None:
        modes = read_modes(config_path) if config_path.exists() else {}

    header = (
        "# autosync_repos.txt — one repo per line, bare name resolves\n"
        "# under ~/Documents/lab/active/. Lines starting with # are ignored.\n"
        "#\n"
        "# Add 'push-only' after a repo to push existing commits without\n"
        "# committing the working tree. Use it for anything actively worked on.\n"
    )
    lines = []
    for repo in repos:
        flags = modes.get(repo, ())
        lines.append(f"{repo}{'  ' + ' '.join(flags) if flags else ''}")
    body = "\n".join(lines) + ("\n" if lines else "")
    config_path.write_text(header + body)
