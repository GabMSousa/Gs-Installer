from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.core.paths import AppPaths, default_installer_path


@dataclass
class AppConfig:
    """Portable JSON preferences with compatibility aliases for earlier tasks."""

    paths: AppPaths = field(default_factory=AppPaths)
    installers_path: str = field(default_factory=lambda: str(default_installer_path()))
    theme: str = "dark"
    cache_path: str = "./cache"
    log_level: str = "INFO"
    auto_check_updates: bool = True
    last_selected_apps: list[str] = field(default_factory=list)
    selected_cleanup_scripts: list[str] = field(default_factory=list)
    profile: str = ""
    cache_enabled: bool = True

    @property
    def installer_path(self) -> str:
        return self.installers_path

    @installer_path.setter
    def installer_path(self, value: str) -> None:
        self.installers_path = value

    @property
    def selected_installers(self) -> list[str]:
        return self.last_selected_apps

    @selected_installers.setter
    def selected_installers(self, value: list[str]) -> None:
        self.last_selected_apps = value

    @classmethod
    def load(cls) -> "AppConfig":
        paths = AppPaths()
        paths.ensure()
        config = cls(paths=paths)
        if paths.config.exists():
            try:
                data = json.loads(paths.config.read_text(encoding="utf-8"))
                config.installers_path = str(data.get("installers_path", data.get("installer_path", config.installers_path)))
                config.cache_path = str(data.get("cache_path", config.cache_path))
                config.theme = str(data.get("theme", config.theme))
                config.log_level = str(data.get("log_level", config.log_level)).upper()
                config.auto_check_updates = bool(data.get("auto_check_updates", config.auto_check_updates))
                config.last_selected_apps = [str(item) for item in data.get("last_selected_apps", data.get("selected_installers", []))]
                config.selected_cleanup_scripts = [str(item) for item in data.get("selected_cleanup_scripts", [])]
                config.profile = str(data.get("profile", config.profile))
                config.cache_enabled = bool(data.get("cache_enabled", config.cache_enabled))
            except (OSError, ValueError, TypeError):
                pass
        config._apply_cache_path()
        return config

    def _apply_cache_path(self) -> None:
        candidate = Path(self.cache_path)
        self.paths.cache = candidate if candidate.is_absolute() else self.paths.root / candidate

    def validate_installers_path(self, create: bool = True) -> tuple[bool, str]:
        path = Path(self.installers_path).expanduser()
        try:
            if path.exists() and path.is_dir():
                return True, f"Pasta disponível: {path}"
            if create:
                path.mkdir(parents=True, exist_ok=True)
                return True, f"Pasta criada: {path}"
            return False, f"A pasta não existe: {path}"
        except OSError as exc:
            return False, f"Não foi possível preparar a pasta {path}: {exc}"

    def save(self) -> None:
        self._apply_cache_path()
        self.paths.ensure()
        payload = {
            "installers_path": self.installers_path,
            "theme": self.theme,
            "cache_path": self.cache_path,
            "log_level": self.log_level,
            "auto_check_updates": self.auto_check_updates,
            "last_selected_apps": self.last_selected_apps,
            "selected_cleanup_scripts": self.selected_cleanup_scripts,
            "profile": self.profile,
            "cache_enabled": self.cache_enabled,
        }
        self.paths.config.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
