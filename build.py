"""Reproducible Windows one-file build for GS Installer."""

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
        "--onefile",
        "--windowed",
        "--name",
        "NiniteTool",
        "--add-data",
        "src/data;src/data",
        "--add-data",
        "scripts;scripts",
        "--add-data",
        "app/assets;app/assets",
        "--add-data",
        "config.json;.",
        str(ENTRYPOINT),
    ]
    print("Executando:", " ".join(command))
    completed = subprocess.run(command, cwd=ROOT, check=False)
    if completed.returncode == 0:
        output = DIST_DIR / "NiniteTool.exe"
        print(f"Build concluído: {output}")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
