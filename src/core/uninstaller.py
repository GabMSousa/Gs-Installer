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
Progress = Callable[[int, int], None]

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
                                    display_icon=self._value(child, "DisplayIcon"),
                                    size_kb=size,
                                    registry_hive=hive_name,
                                ))
                        except OSError:
                            continue
            except OSError as exc:
                LOGGER.warning("Registry scan failed for %s: %s", root, exc)
        return sorted(programs, key=lambda program: program.name.casefold())

    def uninstall_many(self, programs: Iterable[InstalledProgram], deep: bool, force: bool, emit: Emit, progress: Progress | None = None) -> list[UninstallReport]:
        reports: list[UninstallReport] = []
        selected = list(programs)
        for index, program in enumerate(selected, start=1):
            emit(f"[{index}/{len(selected)}] Iniciando: {program.name}")
            reports.append(self.uninstall(program, deep=deep, force=force, emit=emit))
            if progress:
                progress(index, len(selected))
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
                official_ok = return_code in {0, 3010}
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
        if program.display_icon:
            icon_path = Path(os.path.expandvars(program.display_icon.split(",", 1)[0].strip('"')))
            if icon_path.exists() and icon_path.is_file():
                parent = icon_path.parent
                if self._safe_directory(parent) and self._matches(parent.name, self._name_tokens(program)):
                    candidates.append(parent)
        tokens = self._name_tokens(program)
        for raw_root in roots:
            if not raw_root:
                continue
            root = Path(raw_root)
            if not root.exists():
                continue
            candidates.extend(self._scan_root(root, tokens, candidates))
        return candidates

    @classmethod
    def _scan_root(cls, root: Path, tokens: set[str], existing: list[Path], max_depth: int = 4) -> list[Path]:
        """Find named residual files/directories without deleting broad vendor roots."""
        found: list[Path] = []
        root_depth = len(root.parts)
        try:
            for current, directories, files in os.walk(root, topdown=True, followlinks=False):
                current_path = Path(current)
                depth = len(current_path.parts) - root_depth
                matching_dirs = [current_path / name for name in directories if cls._matches(name, tokens)]
                for candidate in matching_dirs:
                    if candidate not in existing and candidate not in found:
                        found.append(candidate)
                directories[:] = [name for name in directories if current_path / name not in matching_dirs]
                if depth >= max_depth:
                    directories[:] = []
                for name in files:
                    candidate = current_path / name
                    if cls._matches(name, tokens) and candidate not in existing and candidate not in found:
                        found.append(candidate)
        except OSError:
            return found
        return found

    def scan_registry_residuals(self, program: InstalledProgram) -> list[RegistryCandidate]:
        if os.name != "nt":
            return []
        import winreg

        hives = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}
        tokens = self._name_tokens(program)
        locations = list(UNINSTALL_PATHS) + [("HKLM", r"SOFTWARE"), ("HKCU", r"SOFTWARE")]
        candidates: list[RegistryCandidate] = []
        if program.registry_key and program.registry_hive in hives:
            parent_path, _, key_name = program.registry_key.rpartition("\\")
            if parent_path and key_name:
                candidates.append(RegistryCandidate(program.registry_hive, parent_path, key_name, key_name))
        for hive_name, root in locations:
            try:
                with winreg.OpenKey(hives[hive_name], root) as parent:
                    for index in range(winreg.QueryInfoKey(parent)[0]):
                        child_name = winreg.EnumKey(parent, index)
                        if self._matches(child_name, tokens):
                            candidate = RegistryCandidate(hive_name, root, child_name, child_name)
                            if candidate not in candidates:
                                candidates.append(candidate)
            except OSError:
                continue
        return candidates

    def remove_file_residuals(self, candidates: Iterable[Path], emit: Emit) -> list[str]:
        removed: list[str] = []
        for candidate in candidates:
            if not self._safe_path(candidate):
                emit(f"Não removido por segurança: {candidate}")
                continue
            try:
                if candidate.is_dir():
                    shutil.rmtree(candidate)
                else:
                    candidate.unlink()
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
        if len(token) < 4:
            return set()
        generic = {"microsoft", "adobe", "google", "apple", "intel", "company", "corporation", "apps", "desktop", "update", "runtime"}
        words = [UninstallerManager._slug(word) for word in re.findall(r"[A-Za-z0-9]+", program.name)]
        compounds = {word for word in words if len(word) >= 5 and word not in generic}
        return {token, *compounds}

    @staticmethod
    def _matches(value: str, tokens: set[str]) -> bool:
        normalized = UninstallerManager._slug(value)
        return any(token in normalized for token in tokens)

    @staticmethod
    def _slug(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.casefold())

    @staticmethod
    def _approved_roots() -> list[Path]:
        roots = [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"), os.environ.get("APPDATA"), os.environ.get("LOCALAPPDATA"), os.environ.get("ProgramData")]
        return [Path(root).resolve() for root in roots if root]

    @classmethod
    def _safe_directory(cls, path: Path) -> bool:
        try:
            resolved = path.resolve()
            if not resolved.exists() or not resolved.is_dir() or len(resolved.parts) <= 2:
                return False
            return any(root != resolved and root in resolved.parents for root in cls._approved_roots())
        except OSError:
            return False

    @classmethod
    def _safe_path(cls, path: Path) -> bool:
        try:
            if path.is_symlink():
                return False
            resolved = path.resolve()
            if not resolved.exists() or len(resolved.parts) <= 2:
                return False
            return any(root != resolved and root in resolved.parents for root in cls._approved_roots())
        except OSError:
            return False

    @staticmethod
    def _registry_label(candidate: RegistryCandidate) -> str:
        return f"{candidate.hive}\\{candidate.parent_path}\\{candidate.key_name}"


__all__ = ["UninstallerManager", "UninstallReport", "RegistryCandidate", "PROTECTED_TOKENS"]
