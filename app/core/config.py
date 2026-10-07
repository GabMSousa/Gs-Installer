from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.core.paths import AppPaths, default_installer_path


@dataclass
class AppConfig:
    paths: AppPaths = field(default_factory=AppPaths)
    theme: str = "dark"
    installer_path: str = field(default_factory=lambda: str(default_installer_path()))
    selected_installers: list[str] = field(default_factory=list)
    selected_cleanup_scripts: list[str] = field(default_factory=list)
    profile: str = ""

    @classmethod
    def load(cls) -> "AppConfig":
        paths = AppPaths()
        paths.ensure()
        config = cls(paths=paths)
        if paths.config.exists():
            try:
                data = json.loads(paths.config.read_text(encoding="utf-8"))
                for key in ("theme", "installer_path", "profile"):
                    if isinstance(data.get(key), str):
                        setattr(config, key, data[key])
                for key in ("selected_installers", "selected_cleanup_scripts"):
                    if isinstance(data.get(key), list):
                        setattr(config, key, [str(item) for item in data[key]])
            except (OSError, ValueError):
                pass
        return config

    def save(self) -> None:
        self.paths.ensure()
        payload = {
            "theme": self.theme,
            "installer_path": self.installer_path,
            "selected_installers": self.selected_installers,
            "selected_cleanup_scripts": self.selected_cleanup_scripts,
            "profile": self.profile,
        }
        self.paths.config.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
