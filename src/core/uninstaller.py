"""Windows inventory and guarded deep-uninstall orchestration."""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from app.models import InstalledProgram

LOGGER = logging.getLogger(__name__)
Emit = Callable[[str], None]

UNINSTALL_PATHS = (
    ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ("HKLM", r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    ("HKCU", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
)
PROTECTED_TOKENS = (
    "windowsdefender",
    "windowssecurity",
    "windowsfirewall",
    "windowsupdate",
    "securityhealth",
    "microsoftdefender",
)


@dataclass(frozen=True)
class RegistryCandidate:
    hive: str
    parent_path: str
    key_name: str
    display: str


@dataclass(frozen=True)
class UninstallReport:
    program: str
    protected: bool
    official_return_code: int | None
    file_candidates: tuple[str, ...]
    files_removed: tuple[str, ...]
    registry_candidates: tuple[str, ...]
    registry_removed: tuple[str, ...]
    message: str


class UninstallerManager:
    def __init__(self, timeout_seconds: int = 1800) -> None:
        self.timeout_seconds = timeout_seconds

    def list_programs(self) -> list[InstalledProgram]:
        if os.name != "nt":
            return []
        import winreg

        hives = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}
        programs: list[InstalledProgram] = []
        for hive_name, root in UNINSTALL_PATHS:
            try:
                with winreg.OpenKey(hives[hive_name], root) as parent:
                    for index in range(winreg.QueryInfoKey(parent)[0]):
                        try:
                            child_name = winreg.EnumKey(parent, index)
                            with winreg.OpenKey(parent, child_name) as child:
                                name = self._value(child, "DisplayName")
                                if not name:
                                    continue
                                size = self._value_int(child, "EstimatedSize")
                                programs.append(InstalledProgram(
                                    name=name,
                                    version=self._value(child, "DisplayVersion"),
                                    publisher=self._value(child, "Publisher"),
                                    uninstall_string=self._value(child, "UninstallString"),
                                    install_location=self._value(child, "InstallLocation"),
                                    registry_key=f"{root}\\{child_name}",
                                    quiet_uninstall_string=self._value(child, "QuietUninstallString"),
                                    size_kb=size,
                                    registry_hive=hive_name,
                                ))
                        except OSError:
                            continue
            except OSError as exc:
                LOGGER.warning("Registry scan failed for %s: %s", root, exc)
        return sorted(programs, key=lambda program: program.name.casefold())

    def uninstall_many(self, programs: Iterable[InstalledProgram], deep: bool, force: bool, emit: Emit) -> list[UninstallReport]:
        reports: list[UninstallReport] = []
        for program in programs:
            reports.append(self.uninstall(program, deep=deep, force=force, emit=emit))
        return reports

    def uninstall(self, program: InstalledProgram, deep: bool, force: bool, emit: Emit) -> UninstallReport:
        if self.is_protected(program):
            message = "programa protegido; nenhuma alteração foi realizada"
            emit(f"{program.name}: {message}")
            return UninstallReport(program.name, True, None, (), (), (), (), message)

        command = program.quiet_uninstall_string or program.uninstall_string
        return_code: int | None = None
        official_ok = False
        if command:
            emit(f"{program.name}: executando desinstalador oficial")
            try:
                completed = subprocess.run(command, shell=True, timeout=self.timeout_seconds, check=False, capture_output=True, text=True)
                return_code = completed.returncode
                official_ok = return_code == 0
                if completed.stdout:
                    emit(completed.stdout[-1000:].strip())
                if completed.stderr:
                    emit(completed.stderr[-1000:].strip())
                emit(f"{program.name}: desinstalador oficial retornou {return_code}")
            except (OSError, subprocess.TimeoutExpired) as exc:
                emit(f"{program.name}: falha no desinstalador oficial: {exc}")
        elif not force:
            message = "sem UninstallString; ative desinstalação forçada para continuar"
            emit(f"{program.name}: {message}")
            return UninstallReport(program.name, False, None, (), (), (), (), message)

        if not official_ok and not force and command:
            message = "desinstalador oficial falhou; resíduos não foram removidos"
            emit(f"{program.name}: {message}")
            return UninstallReport(program.name, False, return_code, (), (), (), (), message)

        file_candidates = self.scan_file_residuals(program)
        registry_candidates = self.scan_registry_residuals(program)
        for candidate in file_candidates:
            emit(f"{program.name}: resíduo encontrado: {candidate}")
        for candidate in registry_candidates:
            emit(f"{program.name}: chave encontrada: {candidate.hive}\\{candidate.parent_path}\\{candidate.key_name}")

        files_removed: list[str] = []
        registry_removed: list[str] = []
        if deep:
            files_removed = self.remove_file_residuals(file_candidates, emit)
            registry_removed = self.remove_registry_residuals(registry_candidates, emit)
        message = f"concluído; {len(file_candidates)} arquivo(s) candidato(s), {len(registry_candidates)} chave(s) candidata(s)"
        if deep:
            message += f"; removidos {len(files_removed)} arquivo(s) e {len(registry_removed)} chave(s)"
        emit(f"{program.name}: {message}")
        return UninstallReport(program.name, False, return_code, tuple(map(str, file_candidates)), tuple(files_removed), tuple(self._registry_label(c) for c in registry_candidates), tuple(registry_removed), message)

    def is_protected(self, program: InstalledProgram) -> bool:
        value = self._slug(program.name)
        return any(token in value for token in PROTECTED_TOKENS)

    def scan_file_residuals(self, program: InstalledProgram) -> list[Path]:
        roots = [
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramFiles(x86)"),
            os.environ.get("APPDATA"),
            os.environ.get("LOCALAPPDATA"),
            os.environ.get("ProgramData"),
        ]
        candidates: list[Path] = []
        if program.install_location:
            location = Path(program.install_location.strip('"'))
            if self._safe_directory(location):
                candidates.append(location)
        tokens = self._name_tokens(program)
        for raw_root in roots:
            if not raw_root:
                continue
            root = Path(raw_root)
            if not root.exists():
                continue
            try:
                for child in root.iterdir():
                    if child.is_dir() and self._matches(child.name, tokens) and child not in candidates:
                        candidates.append(child)
            except OSError:
                continue
        return candidates

    def scan_registry_residuals(self, program: InstalledProgram) -> list[RegistryCandidate]:
        if os.name != "nt":
            return []
        import winreg

        hives = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}
        tokens = self._name_tokens(program)
        locations = list(UNINSTALL_PATHS) + [("HKLM", r"SOFTWARE"), ("HKCU", r"SOFTWARE")]
        candidates: list[RegistryCandidate] = []
        for hive_name, root in locations:
            try:
                with winreg.OpenKey(hives[hive_name], root) as parent:
                    for index in range(winreg.QueryInfoKey(parent)[0]):
                        child_name = winreg.EnumKey(parent, index)
                        if self._matches(child_name, tokens):
                            candidates.append(RegistryCandidate(hive_name, root, child_name, child_name))
            except OSError:
                continue
        return candidates

    def remove_file_residuals(self, candidates: Iterable[Path], emit: Emit) -> list[str]:
        removed: list[str] = []
        for candidate in candidates:
            if not self._safe_directory(candidate):
                emit(f"Não removido por segurança: {candidate}")
                continue
            try:
                shutil.rmtree(candidate)
                removed.append(str(candidate))
                emit(f"Removido: {candidate}")
            except OSError as exc:
                emit(f"Não removido {candidate}: {exc}")
        return removed

    def remove_registry_residuals(self, candidates: Iterable[RegistryCandidate], emit: Emit) -> list[str]:
        if os.name != "nt":
            return []
        import winreg

        hives = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}
        removed: list[str] = []
        for candidate in candidates:
            try:
                with winreg.OpenKey(hives[candidate.hive], candidate.parent_path, access=winreg.KEY_READ | winreg.KEY_WRITE) as parent:
                    self._delete_tree(parent, candidate.key_name)
                label = self._registry_label(candidate)
                removed.append(label)
                emit(f"Chave removida: {label}")
            except OSError as exc:
                emit(f"Chave não removida {candidate.key_name}: {exc}")
        return removed

    @staticmethod
    def _delete_tree(parent, name: str) -> None:
        import winreg

        with winreg.OpenKey(parent, name, access=winreg.KEY_READ | winreg.KEY_WRITE) as key:
            while winreg.QueryInfoKey(key)[0]:
                child = winreg.EnumKey(key, 0)
                UninstallerManager._delete_tree(key, child)
        winreg.DeleteKey(parent, name)

    @staticmethod
    def _value(key, name: str) -> str:
        try:
            import winreg
            return str(winreg.QueryValueEx(key, name)[0] or "")
        except OSError:
            return ""

    @staticmethod
    def _value_int(key, name: str) -> int | None:
        try:
            import winreg
            value = winreg.QueryValueEx(key, name)[0]
            return int(value) if value else None
        except (OSError, TypeError, ValueError):
            return None

    @staticmethod
    def _name_tokens(program: InstalledProgram) -> set[str]:
        # Do not use publisher names for filesystem deletion: a vendor such as
        # Microsoft or Google would otherwise match an entire shared folder.
        token = UninstallerManager._slug(program.name)
        return {token} if len(token) >= 4 else set()

    @staticmethod
    def _matches(value: str, tokens: set[str]) -> bool:
        normalized = UninstallerManager._slug(value)
        return any(token in normalized for token in tokens)

    @staticmethod
    def _slug(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.casefold())

    @staticmethod
    def _safe_directory(path: Path) -> bool:
        try:
            resolved = path.resolve()
            return resolved.exists() and resolved.is_dir() and len(resolved.parts) > 2
        except OSError:
            return False

    @staticmethod
    def _registry_label(candidate: RegistryCandidate) -> str:
        return f"{candidate.hive}\\{candidate.parent_path}\\{candidate.key_name}"


__all__ = ["UninstallerManager", "UninstallReport", "RegistryCandidate", "PROTECTED_TOKENS"]
