"""PyInstaller entry point — runs outside the app/ package so app.main's
relative imports resolve correctly (a script run directly has no package)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import main

if __name__ == "__main__":
    main()
