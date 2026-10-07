from __future__ import annotations

import os
import sys
from pathlib import Path


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def bundle_root() -> Path:
    """Return the resource root extracted by PyInstaller one-file builds."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", app_root()))
    return app_root()


def default_installer_path() -> Path:
    return Path(os.environ.get("GS_INSTALLER_PATH", r"D:\Ferramentas\Instaladores"))


class AppPaths:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or app_root()
        self.bundle = bundle_root()
        self.cache = self.root / "cache"
        external_scripts = self.root / "scripts" / "winscript"
        bundled_scripts = self.bundle / "scripts" / "winscript"
        self.scripts = external_scripts if external_scripts.exists() else bundled_scripts
        self.logs = self.root / "logs"
        self.config = self.root / "config.json"
        self.bundled_config = self.bundle / "config.json"

    def ensure(self) -> None:
        paths = [self.cache, self.logs]
        if self.scripts != self.bundle / "scripts" / "winscript":
            paths.append(self.scripts)
        for path in paths:
            path.mkdir(parents=True, exist_ok=True)
