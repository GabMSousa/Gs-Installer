"""Core batch-installation orchestration for GS Installer.

This module owns orchestration and process execution only. Download resolution
remains behind ``DownloadService`` so the cache/provider work from the next task
can evolve without changing the install workflow.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable

from app.data.catalog import CATALOG
from app.models import SoftwareItem
from app.services.downloads import DownloadService

LOGGER = logging.getLogger(__name__)
Emit = Callable[[str], None]


class InstallationStatus(str, Enum):
    SUCCESS = "sucesso"
    FAILED = "falha"
    ALREADY_INSTALLED = "já instalado"


@dataclass(frozen=True)
class InstallationResult:
    program: str
    status: InstallationStatus
    message: str
    installer: str = ""
    return_code: int | None = None


SILENT_ARGUMENTS: dict[str, tuple[str, ...]] = {
    "chrome": ("/silent", "/install"),
    "firefox": ("/S",),
    "7zip": ("/S",),
    "vlc": ("/S",),
    "notepadpp": ("/S",),
    "python": ("/quiet", "InstallAllUsers=1", "PrependPath=1", "Include_test=0"),
    "nodejs": ("/quiet",),
    "vscode": ("/VERYSILENT", "/NORESTART"),
    "discord": ("-s",),
    "telegram": ("/VERYSILENT",),
}

SUCCESS_CODES = {0, 3010}
UNINSTALL_REGISTRY_PATHS = (
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
    r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
)


class InstallerManager:
    """Install selected catalog entries while isolating failures per program."""

    def __init__(self, downloader: DownloadService, installer_dir: Path | str, timeout_seconds: int = 1800, emit: Emit | None = None) -> None:
        self.downloader = downloader
        self.installer_dir = Path(installer_dir)
        self.timeout_seconds = timeout_seconds
        self.emit = emit or (lambda message: LOGGER.info(message))

    def install_selected(self, programs: Iterable[SoftwareItem | str | dict], emit: Emit | None = None) -> list[InstallationResult]:
        """Install every selected item and continue after individual failures."""
        report: list[InstallationResult] = []
        write = emit or self.emit
        for selected in programs:
            item = self._coerce_item(selected)
            try:
                result = self.install_one(item, emit=write)
            except Exception as exc:
                LOGGER.exception("Unexpected installer failure for %s", item.slug)
                result = InstallationResult(item.name, InstallationStatus.FAILED, f"erro inesperado: {exc}")
                write(f"{item.name}: {result.message}")
            report.append(result)
        return report

    def install_one(self, item: SoftwareItem, emit: Emit | None = None) -> InstallationResult:
        write = emit or self.emit
        if self.is_already_installed(item):
            message = "já está instalado; instalação ignorada"
            write(f"{item.name}: {message}")
            return InstallationResult(item.name, InstallationStatus.ALREADY_INSTALLED, message)
        try:
            installer_path, source_message = self._resolve_installer(item)
            write(f"{item.name}: {source_message}")
            if installer_path is None:
                message = f"instalador não encontrado; fonte oficial: {item.official_url}"
                write(f"{item.name}: {message}")
                return InstallationResult(item.name, InstallationStatus.FAILED, message)
            command = self.build_command(item, installer_path)
            write(f"{item.name}: executando instalação silenciosa ({installer_path.name})")
            completed = subprocess.run(command, capture_output=True, text=True, timeout=self.timeout_seconds, check=False)
            output = (completed.stdout or completed.stderr or "").strip()
            if output:
                write(f"{item.name}: {output[-1000:]}")
            if completed.returncode not in SUCCESS_CODES:
                message = f"instalação falhou com código {completed.returncode}"
                write(f"{item.name}: {message}")
                return InstallationResult(item.name, InstallationStatus.FAILED, message, str(installer_path), completed.returncode)
            message = "instalação concluída" + ("; reinicialização recomendada" if completed.returncode == 3010 else "")
            write(f"{item.name}: {message}")
            return InstallationResult(item.name, InstallationStatus.SUCCESS, message, str(installer_path), completed.returncode)
        except subprocess.TimeoutExpired:
            message = f"tempo limite excedido ({self.timeout_seconds}s)"
            LOGGER.exception("Installer timeout for %s", item.slug)
            write(f"{item.name}: {message}")
            return InstallationResult(item.name, InstallationStatus.FAILED, message)
        except (OSError, RuntimeError, ValueError) as exc:
            LOGGER.exception("Installer error for %s", item.slug)
            message = f"erro: {exc}"
            write(f"{item.name}: {message}")
            return InstallationResult(item.name, InstallationStatus.FAILED, message)

    def _resolve_installer(self, item: SoftwareItem) -> tuple[Path | None, str]:
        local = self.find_local_installer(item)
        if local is not None and self.is_local_installer_current(local):
            return local, f"instalador local encontrado: {local.name}"
        if local is not None:
            self.emit(f"{item.name}: instalador local sem metadados de versão; buscando provider oficial")
            try:
                release = self.downloader.github_asset(item)
                if release is not None:
                    return release, f"release oficial baixado para o cache: {release.name}"
            except Exception as exc:
                LOGGER.warning("Official fallback failed for %s: %s", item.slug, exc)
            return None, "instalador local inválido e nenhum asset oficial disponível"
        return self.downloader.acquire(item, self.installer_dir)

    def find_local_installer(self, item: SoftwareItem) -> Path | None:
        if not self.installer_dir.exists():
            return None
        tokens = {self._slug(item.slug), self._slug(item.name)}
        candidates = [
            path for path in self.installer_dir.iterdir()
            if path.is_file() and path.suffix.lower() in {".exe", ".msi"}
            and any(token and token in self._slug(path.stem) for token in tokens)
        ]
        return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)[0] if candidates else None

    @staticmethod
    def is_local_installer_current(path: Path) -> bool:
        """Use a non-empty artifact until provider version/hash metadata exists."""
        try:
            return path.is_file() and path.stat().st_size > 0
        except OSError:
            return False

    def is_already_installed(self, item: SoftwareItem) -> bool:
        names = {self._slug(item.slug), self._slug(item.name)}
        if os.name == "nt" and self._registry_contains(names):
            return True
        return any(path.exists() for path in self._common_install_paths(item))

    def _registry_contains(self, names: set[str]) -> bool:
        try:
            import winreg
            for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                for root in UNINSTALL_REGISTRY_PATHS:
                    try:
                        with winreg.OpenKey(hive, root) as parent:
                            for index in range(winreg.QueryInfoKey(parent)[0]):
                                try:
                                    with winreg.OpenKey(parent, winreg.EnumKey(parent, index)) as key:
                                        value = str(winreg.QueryValueEx(key, "DisplayName")[0] or "")
                                        normalized = self._slug(value)
                                        if any(name and (name in normalized or normalized in name) for name in names):
                                            return True
                                except OSError:
                                    continue
                    except OSError:
                        continue
        except ImportError:
            return False
        return False

    @staticmethod
    def _common_install_paths(item: SoftwareItem) -> list[Path]:
        roots = [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"), os.environ.get("LOCALAPPDATA"), os.environ.get("APPDATA")]
        return [Path(root) / label for root in roots if root for label in (item.name, item.slug)]

    @staticmethod
    def build_command(item: SoftwareItem, installer_path: Path) -> list[str]:
        if installer_path.suffix.lower() == ".msi":
            return ["msiexec.exe", "/i", str(installer_path), "/qn", "/norestart"]
        arguments = SILENT_ARGUMENTS.get(item.slug.lower(), item.silent_args or ("/S",))
        return [str(installer_path), *arguments]

    @staticmethod
    def _slug(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.lower())

    @staticmethod
    def _coerce_item(selected: SoftwareItem | str | dict) -> SoftwareItem:
        if isinstance(selected, SoftwareItem):
            return selected
        if isinstance(selected, dict):
            return SoftwareItem(str(selected.get("slug", selected.get("id", ""))), str(selected["name"]), str(selected.get("category", "")), str(selected.get("official_url", "")), github_repo=selected.get("github_repo"))
        value = str(selected)
        normalized = InstallerManager._slug(value)
        for item in CATALOG:
            if item.slug == value or InstallerManager._slug(item.name) == normalized:
                return item
        return SoftwareItem(normalized, value, "", "")


__all__ = ["InstallerManager", "InstallationResult", "InstallationStatus", "SILENT_ARGUMENTS"]
