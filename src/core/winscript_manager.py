"""WinScript acquisition, discovery, preview and cancellable execution."""

from __future__ import annotations

import logging
import subprocess
import threading
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from src.core.downloader import Downloader

LOGGER = logging.getLogger(__name__)
REPO_ZIP = "https://github.com/flick9000/winscript/archive/refs/heads/main.zip"
Emit = Callable[[str], None]
Progress = Callable[[int, int], None]


@dataclass(frozen=True)
class ScriptExecutionResult:
    script: Path
    status: str
    return_code: int | None = None
    message: str = ""


class WinScriptManager:
    SCRIPT_SUFFIXES = {".ps1", ".bat", ".cmd"}

    def __init__(self, cache_dir: Path | str, scripts_dir: Path | str, timeout_seconds: int = 900) -> None:
        self.cache_dir = Path(cache_dir)
        self.scripts_dir = Path(scripts_dir)
        self.timeout_seconds = timeout_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def list_scripts(self) -> list[Path]:
        """List every executable script while preserving the repository tree."""
        if not self.scripts_dir.exists():
            return []
        return sorted(path for path in self.scripts_dir.rglob("*") if path.is_file() and path.suffix.casefold() in self.SCRIPT_SUFFIXES)

    def category_for(self, script: Path) -> str:
        """Use the first meaningful repository folder as the UI category."""
        try:
            relative = script.relative_to(self.scripts_dir)
        except ValueError:
            return "Geral"
        parts = tuple(part for part in relative.parts[:-1] if part.lower() not in {"winscript-main", "winscript-master"})
        return parts[0].replace("_", " ").title() if parts else "Geral"

    def ensure_available(self, emit: Emit, progress: Progress | None = None) -> list[Path]:
        scripts = self.list_scripts()
        if scripts:
            emit(f"WinScript offline: {len(scripts)} scripts disponíveis")
            return scripts
        archive = self.cache_dir / "winscript-main.zip"
        emit("Baixando WinScript da fonte oficial do GitHub…")
        downloader = Downloader(self.cache_dir, timeout_seconds=60, max_retries=3, emit=emit)
        result = downloader.download(REPO_ZIP, "winscript-main.zip", progress=progress, emit=emit)
        self._safe_extract(result.path, self.scripts_dir)
        scripts = self.list_scripts()
        emit(f"WinScript pronto para uso offline: {len(scripts)} scripts")
        return scripts

    def preview(self, script: Path) -> str:
        try:
            content = script.read_text(encoding="utf-8", errors="replace")
            return content[:10000]
        except OSError as exc:
            return f"Não foi possível ler o script: {exc}"

    def execute_selected(
        self,
        scripts: Iterable[Path],
        emit: Emit,
        progress: Progress | None = None,
        cancel_event: threading.Event | None = None,
    ) -> list[ScriptExecutionResult]:
        selected = list(scripts)
        results: list[ScriptExecutionResult] = []
        for index, script in enumerate(selected, start=1):
            if cancel_event and cancel_event.is_set():
                emit("Execução cancelada antes do próximo script.")
                break
            result = self.execute(script, emit, cancel_event=cancel_event)
            results.append(result)
            if progress:
                progress(index, len(selected))
            if result.status == "cancelado":
                break
        return results

    def execute(self, script: Path, emit: Emit, cancel_event: threading.Event | None = None) -> ScriptExecutionResult:
        emit(f"Executando {script.name} ({self.category_for(script)})…")
        if script.suffix.casefold() == ".ps1":
            command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)]
        else:
            command = ["cmd.exe", "/d", "/c", str(script)]
        process: subprocess.Popen[str] | None = None
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            assert process.stdout is not None
            while True:
                if cancel_event and cancel_event.is_set():
                    process.terminate()
                    emit(f"{script.name}: cancelado pelo usuário")
                    return ScriptExecutionResult(script, "cancelado", message="cancelado pelo usuário")
                line = process.stdout.readline()
                if line:
                    emit(line.rstrip())
                elif process.poll() is not None:
                    break
            return_code = process.wait(timeout=self.timeout_seconds)
            status = "sucesso" if return_code == 0 else "falha"
            emit(f"{script.name}: código {return_code}")
            return ScriptExecutionResult(script, status, return_code)
        except subprocess.TimeoutExpired:
            if process:
                process.kill()
            emit(f"{script.name}: tempo limite excedido ({self.timeout_seconds}s)")
            return ScriptExecutionResult(script, "falha", message="tempo limite excedido")
        except OSError as exc:
            emit(f"{script.name}: erro ao iniciar PowerShell: {exc}")
            return ScriptExecutionResult(script, "falha", message=str(exc))

    @staticmethod
    def _safe_extract(archive: Path, destination: Path) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        root = destination.resolve()
        with zipfile.ZipFile(archive) as zipped:
            for member in zipped.infolist():
                target = (destination / member.filename).resolve()
                if root not in target.parents and target != root:
                    raise RuntimeError(f"entrada insegura no arquivo WinScript: {member.filename}")
            zipped.extractall(destination)


__all__ = ["WinScriptManager", "ScriptExecutionResult"]
