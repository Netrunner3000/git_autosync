"""Read/write the autosync repo list (one repo name/path per line)."""
from pathlib import Path


def read_repos(config_path: Path) -> list[str]:
    repos = []
    for line in config_path.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            repos.append(line)
    return repos


def write_repos(config_path: Path, repos: list[str]) -> None:
    header = (
        "# autosync_repos.txt — one repo per line, bare name resolves\n"
        "# under ~/Documents/lab/active/. Lines starting with # are ignored.\n"
    )
    body = "\n".join(repos) + ("\n" if repos else "")
    config_path.write_text(header + body)
