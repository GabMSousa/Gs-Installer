"""Reproducible Windows onedir build for NiniteTool."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BUILD_DIR = ROOT / "build"
DIST_DIR = ROOT / "dist"
ENTRYPOINT = ROOT / "app" / "main.py"


def clean() -> None:
    for target in (BUILD_DIR, DIST_DIR):
        if target.exists():
            resolved = target.resolve()
            if resolved.parent != ROOT.resolve():
                raise RuntimeError(f"caminho de build inesperado: {resolved}")
            shutil.rmtree(resolved)


def main() -> int:
    clean()
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name",
        "NiniteTool",
        "--add-data",
        "src/data;src/data",
        "--add-data",
        "scripts;scripts",
        "--add-data",
        "config.json;.",
        str(ENTRYPOINT),
    ]
    print("Executando:", " ".join(command))
    completed = subprocess.run(command, cwd=ROOT, check=False)
    if completed.returncode == 0:
        output_dir = DIST_DIR / "NiniteTool"
        # PyInstaller 6 stores --add-data files in _internal. The application
        # intentionally keeps mutable portable state beside the executable.
        runtime_config = output_dir / "config.json"
        shutil.copy2(ROOT / "config.json", runtime_config)
        runtime_scripts = output_dir / "scripts"
        if runtime_scripts.exists():
            shutil.rmtree(runtime_scripts)
        shutil.copytree(ROOT / "scripts", runtime_scripts)
        print(f"Build concluído: {DIST_DIR / 'NiniteTool' / 'NiniteTool.exe'}")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
