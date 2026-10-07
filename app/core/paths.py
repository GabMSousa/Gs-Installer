from __future__ import annotations

import os
import sys
from pathlib import Path


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def default_installer_path() -> Path:
    return Path(os.environ.get("GS_INSTALLER_PATH", r"D:\Ferramentas\Instaladores"))


class AppPaths:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or app_root()
        self.cache = self.root / "cache"
        self.scripts = self.root / "scripts" / "winscript"
        self.logs = self.root / "logs"
        self.config = self.root / "config.json"

    def ensure(self) -> None:
        for path in (self.cache, self.scripts, self.logs):
            path.mkdir(parents=True, exist_ok=True)
