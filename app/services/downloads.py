"""Compatibility import for services created before Tarefa 03."""

from src.core.downloader import DownloadResult, Downloader


class DownloadService(Downloader):
    """Legacy name retained for the existing UI and installer manager."""

    pass


__all__ = ["Downloader", "DownloadResult", "DownloadService"]
