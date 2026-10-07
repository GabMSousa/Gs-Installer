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


__all__ = ["InstallerManager", "InstallerService"]
