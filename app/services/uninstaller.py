from __future__ import annotations

import logging
import os
import re
import subprocess
import winreg
from pathlib import Path

from app.models import InstalledProgram

LOGGER = logging.getLogger(__name__)
UNINSTALL_PATHS = (
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
)


class UninstallerService:
    def list_programs(self) -> list[InstalledProgram]:
        if os.name != "nt":
            return []
        programs: list[InstalledProgram] = []
        for hive, root in UNINSTALL_PATHS:
            try:
                with winreg.OpenKey(hive, root) as parent:
                    for index in range(winreg.QueryInfoKey(parent)[0]):
                        try:
                            child_name = winreg.EnumKey(parent, index)
                            with winreg.OpenKey(parent, child_name) as child:
                                name = self._value(child, "DisplayName")
                                if not name:
                                    continue
                                programs.append(InstalledProgram(name, self._value(child, "DisplayVersion"), self._value(child, "Publisher"), self._value(child, "UninstallString"), self._value(child, "InstallLocation"), f"{root}\\{child_name}"))
                        except OSError:
                            continue
            except OSError as exc:
                LOGGER.warning("Registry scan failed: %s", exc)
        return sorted(programs, key=lambda program: program.name.lower())

    @staticmethod
    def _value(key, name: str) -> str:
        try:
            return str(winreg.QueryValueEx(key, name)[0] or "")
        except OSError:
            return ""

    def uninstall(self, program: InstalledProgram, force: bool, emit) -> list[str]:
        removed: list[str] = []
        if program.uninstall_string and not force:
            emit(f"Desinstalador oficial: {program.name}")
            try:
                subprocess.run(program.uninstall_string, shell=True, timeout=1800, check=False)
            except (OSError, subprocess.TimeoutExpired) as exc:
                emit(f"Falha no desinstalador oficial: {exc}")
        elif force:
            emit(f"Desinstalação forçada solicitada: {program.name}")
        for candidate in self.residual_candidates(program):
            emit(f"Residual candidato: {candidate}")
            if force and candidate.exists() and candidate.is_dir():
                try:
                    import shutil
                    shutil.rmtree(candidate)
                    removed.append(str(candidate))
                except OSError as exc:
                    emit(f"Não removido: {exc}")
        return removed

    @staticmethod
    def residual_candidates(program: InstalledProgram) -> list[Path]:
        candidates: list[Path] = []
        if program.install_location:
            path = Path(program.install_location.strip('"'))
            if path.is_absolute() and len(path.parts) > 2:
                candidates.append(path)
        for base in (Path(os.environ.get("APPDATA", "")), Path(os.environ.get("LOCALAPPDATA", ""))):
            if base and base.exists():
                candidates.extend(p for p in base.iterdir() if p.is_dir() and re.search(re.escape(program.name), p.name, re.I))
        return candidates
