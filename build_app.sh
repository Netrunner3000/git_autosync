#!/bin/bash
# Builds the standalone "git_autosync.app" with PyInstaller, ad-hoc signs it,
# and installs it into /Applications.
set -euo pipefail
cd "$(dirname "$0")"

source .venv/bin/activate
uv pip install -q -r requirements.txt pyinstaller

rm -rf build dist
pyinstaller --noconfirm packaging/git_autosync.spec

codesign --force --deep -s - dist/git_autosync.app

rm -rf "/Applications/git_autosync.app"
cp -R dist/git_autosync.app /Applications/

echo "Installed: /Applications/git_autosync.app"
echo "First launch from Finder: right-click -> Open (unsigned app, ad-hoc signature only)."
