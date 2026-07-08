# PyInstaller spec for the git_autosync GUI.
# Build with:  pyinstaller packaging/git_autosync.spec
# Output:      dist/git_autosync.app
import os
from pathlib import Path

block_cipher = None

# PyInstaller execs the spec without __file__; SPECPATH is provided instead.
PROJECT_ROOT = Path(SPECPATH).resolve().parent

datas = [
    (str(PROJECT_ROOT / "git_autosync.sh"), "."),
    (str(PROJECT_ROOT / "autosync_repos.txt"), "."),
    (str(PROJECT_ROOT / "README.md"), "."),
]

icon_path = PROJECT_ROOT / "packaging" / "icon.icns"
icon = str(icon_path) if icon_path.exists() else None

a = Analysis(
    [str(PROJECT_ROOT / "packaging" / "entry_point.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="git_autosync",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="git_autosync",
)

app = BUNDLE(
    coll,
    name="git_autosync.app",
    icon=icon,
    bundle_identifier="com.netrunner3000.git-autosync",
    info_plist={
        "CFBundleShortVersionString": "1.0.0",
        "NSHighResolutionCapable": True,
    },
)
