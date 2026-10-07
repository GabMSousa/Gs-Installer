from __future__ import annotations

import logging
import subprocess
import urllib.request
import zipfile
from pathlib import Path

from app.services.downloads import DownloadService

LOGGER = logging.getLogger(__name__)
REPO_ZIP = "https://github.com/flick9000/winscript/archive/refs/heads/main.zip"


class WinScriptService:
    def __init__(self, cache_dir: Path, scripts_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.scripts_dir = scripts_dir

    def list_scripts(self) -> list[Path]:
        return sorted(self.scripts_dir.rglob("*.ps1")) if self.scripts_dir.exists() else []

    def ensure_available(self, emit) -> list[Path]:
        scripts = self.list_scripts()
        if scripts:
            emit(f"WinScript offline: {len(scripts)} scripts disponíveis")
            return scripts
        archive = self.cache_dir / "winscript-main.zip"
        emit("Baixando WinScript da fonte oficial do GitHub…")
        request = urllib.request.Request(REPO_ZIP, headers={"User-Agent": "GS-Installer/0.1"})
        with urllib.request.urlopen(request, timeout=60) as response, archive.open("wb") as output:
            output.write(response.read())
        with zipfile.ZipFile(archive) as zipped:
            zipped.extractall(self.scripts_dir)
        scripts = self.list_scripts()
        emit(f"WinScript pronto para uso offline: {len(scripts)} scripts")
        return scripts

    def preview(self, script: Path) -> str:
        try:
            content = script.read_text(encoding="utf-8", errors="replace")
            return content[:5000]
        except OSError as exc:
            return f"Não foi possível ler o script: {exc}"

    def execute(self, script: Path, emit) -> bool:
        emit(f"Executando {script.name}…")
        command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=900, check=False)
            for line in (completed.stdout + "\n" + completed.stderr).splitlines()[-30:]:
                if line.strip():
                    emit(line)
            emit(f"{script.name}: código {completed.returncode}")
            return completed.returncode == 0
        except (OSError, subprocess.TimeoutExpired) as exc:
            emit(f"{script.name}: erro {exc}")
            return False
