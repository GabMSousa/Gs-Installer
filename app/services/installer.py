"""Backward-compatible adapter for the original UI service contract."""

from __future__ import annotations

from pathlib import Path

from app.models import SoftwareItem
from app.services.downloads import DownloadService
from src.core.installer import InstallerManager, InstallationStatus


class InstallerService:
    def __init__(self, downloader: DownloadService) -> None:
        self.downloader = downloader

    def install(self, item: SoftwareItem, installer_dir: Path, emit) -> bool:
        manager = InstallerManager(self.downloader, installer_dir, emit=emit)
        result = manager.install_one(item, emit=emit)
        return result.status in {InstallationStatus.SUCCESS, InstallationStatus.ALREADY_INSTALLED}

    def install_batch(self, items, installer_dir: Path, emit, progress, download_progress, force_reinstall=False):
        manager = InstallerManager(self.downloader, installer_dir, emit=emit)
        return manager.install_selected(items, emit=emit, progress=progress, download_progress=download_progress, force_reinstall=force_reinstall)


__all__ = ["InstallerManager", "InstallerService"]
