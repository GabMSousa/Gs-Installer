"""Official-source downloader with retry, progress and local caching."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.models import SoftwareItem

LOGGER = logging.getLogger(__name__)
Progress = Callable[[int, int], None]
Emit = Callable[[str], None]


@dataclass(frozen=True)
class DownloadResult:
    path: Path
    downloaded_bytes: int
    total_bytes: int | None
    from_cache: bool
    sha256: str


class Downloader:
    """Download official artifacts and keep them reusable in ``cache/``."""

    def __init__(self, cache_dir: Path | str, timeout_seconds: int = 60, max_retries: int = 3, emit: Emit | None = None) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(1, min(max_retries, 3))
        self.emit = emit or (lambda message: LOGGER.info(message))

    def download(
        self,
        url: str,
        filename: str | None = None,
        force: bool = False,
        destination: Path | str | None = None,
        progress: Progress | None = None,
        emit: Emit | None = None,
    ) -> DownloadResult:
        """Download to a temporary file and atomically publish a valid artifact."""

        write = emit or self.emit
        target_dir = Path(destination) if destination else self.cache_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / (filename or self.filename_from_url(url))
        if target.exists() and target.is_file() and target.stat().st_size > 0 and not force:
            size = target.stat().st_size
            write(f"Cache utilizado: {target.name} ({self._format_bytes(size)})")
            return DownloadResult(target, size, size, True, self.sha256(target))

        part = target.with_suffix(target.suffix + ".part")
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                write(f"Download {attempt}/{self.max_retries}: {url}")
                request = urllib.request.Request(url, headers={"User-Agent": "GS-Installer/0.1", "Accept": "application/octet-stream"})
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response, part.open("wb") as output:
                    total_header = response.headers.get("Content-Length")
                    total = int(total_header) if total_header and total_header.isdigit() else 0
                    downloaded = 0
                    last_report = 0
                    while chunk := response.read(1024 * 256):
                        output.write(chunk)
                        downloaded += len(chunk)
                        if progress:
                            progress(downloaded, total)
                        if downloaded - last_report >= 1024 * 1024 or (total and downloaded == total):
                            write(f"{target.name}: {self._format_bytes(downloaded)}" + (f" / {self._format_bytes(total)}" if total else ""))
                            last_report = downloaded
                if downloaded <= 0:
                    raise IOError("arquivo baixado vazio")
                if total and downloaded != total:
                    raise IOError(f"tamanho incompleto: {downloaded} de {total} bytes")
                part.replace(target)
                digest = self.sha256(target)
                write(f"Download concluído: {target.name} ({self._format_bytes(downloaded)})")
                return DownloadResult(target, downloaded, total or None, False, digest)
            except (OSError, IOError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
                last_error = exc
                LOGGER.warning("Download attempt %s failed for %s: %s", attempt, url, exc)
                try:
                    part.unlink(missing_ok=True)
                except OSError:
                    pass
                if attempt < self.max_retries:
                    time.sleep(min(2 ** (attempt - 1), 4))
        raise RuntimeError(f"não foi possível baixar após {self.max_retries} tentativas: {last_error}")

    def github_asset(self, item: SoftwareItem, force: bool = False, progress: Progress | None = None, emit: Emit | None = None) -> Path | None:
        if not item.github_repo:
            return None
        api = f"https://api.github.com/repos/{item.github_repo}/releases/latest"
        request = urllib.request.Request(api, headers={"Accept": "application/vnd.github+json", "User-Agent": "GS-Installer/0.1"})
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            release = json.load(response)
        candidates = [asset for asset in release.get("assets", []) if re.search(r"\.(exe|msi)$", asset.get("name", ""), re.I)]
        if not candidates:
            return None
        # Prefer x64/windows-labelled artifacts, then preserve API ordering.
        candidates.sort(key=lambda asset: ("x64" not in asset.get("name", "").lower(), "win" not in asset.get("name", "").lower()))
        asset = candidates[0]
        result = self.download(asset["browser_download_url"], asset["name"], force=force, progress=progress, emit=emit)
        return result.path

    def acquire(
        self,
        item: SoftwareItem,
        installer_dir: Path | str,
        force: bool = False,
        progress: Progress | None = None,
        emit: Emit | None = None,
    ) -> tuple[Path | None, str]:
        """Resolve local, cached, GitHub-release or direct official artifacts."""

        local_dir = Path(installer_dir)
        local_dir.mkdir(parents=True, exist_ok=True)
        local = self._find_local(item, local_dir)
        if local and not force and local.stat().st_size > 0:
            return local, f"instalador local encontrado: {local.name}"
        try:
            if item.github_repo:
                cached = self.github_asset(item, force=force, progress=progress, emit=emit)
                if cached:
                    return cached, f"release oficial do GitHub em cache: {cached.name}"
            if self.is_direct_artifact_url(item.official_url):
                result = self.download(item.official_url, force=force, progress=progress, emit=emit)
                return result.path, f"download oficial em cache: {result.path.name}"
        except (OSError, RuntimeError, urllib.error.URLError, ValueError) as exc:
            LOGGER.warning("Official download failed for %s: %s", item.slug, exc)
            return None, f"falha no download oficial: {exc}"
        return None, "a fonte oficial é uma página de download; selecione o instalador compatível manualmente"

    def copy_to_installers(self, artifact: Path, installer_dir: Path | str) -> Path:
        destination = Path(installer_dir)
        destination.mkdir(parents=True, exist_ok=True)
        target = destination / artifact.name
        if artifact.resolve() != target.resolve():
            shutil.copy2(artifact, target)
        return target

    @staticmethod
    def _find_local(item: SoftwareItem, directory: Path) -> Path | None:
        tokens = {Downloader._slug(item.slug), Downloader._slug(item.name)}
        candidates = [p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in {".exe", ".msi"} and any(t and t in Downloader._slug(p.stem) for t in tokens)]
        return sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[0] if candidates else None

    @staticmethod
    def filename_from_url(url: str) -> str:
        name = Path(urllib.parse.urlparse(url).path).name or "download.bin"
        return re.sub(r"[^A-Za-z0-9._-]+", "_", name)

    @staticmethod
    def is_direct_artifact_url(url: str) -> bool:
        return bool(re.search(r"\.(exe|msi)(?:$|[?#])", urllib.parse.urlparse(url).path, re.I))

    @staticmethod
    def _slug(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.lower())

    @staticmethod
    def _format_bytes(value: int) -> str:
        if value < 1024 * 1024:
            return f"{value / 1024:.0f} KB"
        return f"{value / (1024 * 1024):.1f} MB"

    @staticmethod
    def sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def extract_winscript(archive: Path, destination: Path) -> list[Path]:
        destination.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as zipped:
            zipped.extractall(destination)
        return [p for p in destination.rglob("*.ps1") if p.is_file()]


__all__ = ["Downloader", "DownloadResult"]
