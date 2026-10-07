"""Compatibility adapter for the deep uninstaller manager."""

from src.core.uninstaller import UninstallReport, UninstallerManager


class UninstallerService(UninstallerManager):
    """Legacy service name retained for the existing GUI."""

    def uninstall(self, program, deep=False, force=False, emit=lambda message: None):
        return super().uninstall(program, deep=deep, force=force, emit=emit)


__all__ = ["UninstallReport", "UninstallerManager", "UninstallerService"]
