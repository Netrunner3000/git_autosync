#!/bin/bash
# Double-click launcher for git_autosync.
# Runs a normal sync of every repo in autosync_repos.txt, then waits.
cd "$(dirname "$0")" || exit 1
./git_autosync.sh "$@"
echo
echo "Done. Press Return to close this window."
read -r _
