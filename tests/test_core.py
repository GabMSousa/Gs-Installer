from __future__ import annotations

import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.models import InstalledProgram, SoftwareItem
from src.core.downloader import Downloader
from src.core.installer import InstallerManager, InstallationStatus
from src.core.uninstaller import UninstallerManager
from src.core.winscript_manager import WinScriptManager


class TestDownloader(unittest.TestCase):
    def test_download_and_cache(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.bin"
            source.write_bytes(b"portable-test")
            downloader = Downloader(root / "cache")
            first = downloader.download(source.as_uri(), "artifact.bin")
            second = downloader.download(source.as_uri(), "artifact.bin")
            self.assertFalse(first.from_cache)
            self.assertTrue(second.from_cache)
            self.assertEqual(first.sha256, second.sha256)


class TestInstaller(unittest.TestCase):
    def test_batch_continues_after_missing_installer(self):
        class FakeDownloader:
            def acquire(self, item, installer_dir, **kwargs):
                return None, "missing"

        manager = InstallerManager(FakeDownloader(), Path("cache"))
        manager.is_already_installed = lambda item: False
        results = manager.install_selected(["7zip", "firefox"])
        self.assertEqual(len(results), 2)
        self.assertTrue(all(result.status == InstallationStatus.FAILED for result in results))

    def test_msi_uses_msiexec(self):
        item = SoftwareItem("demo", "Demo", "", "")
        command = InstallerManager.build_command(item, Path("demo.msi"))
        self.assertEqual(command[:2], ["msiexec.exe", "/i"])
        self.assertIn("/qn", command)


class TestWinScript(unittest.TestCase):
    def test_cancel_before_first_script(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "example.ps1"
            script.write_text("Write-Output 'test'", encoding="utf-8")
            manager = WinScriptManager(root / "cache", root / "scripts")
            event = threading.Event()
            event.set()
            results = manager.execute_selected([script], lambda message: None, cancel_event=event)
            self.assertEqual(results, [])


class TestUninstallerSafety(unittest.TestCase):
    def test_protected_system_program(self):
        manager = UninstallerManager()
        protected = InstalledProgram("Windows Defender", "", "Microsoft", "")
        self.assertTrue(manager.is_protected(protected))
        report = manager.uninstall(protected, deep=True, force=True, emit=lambda message: None)
        self.assertTrue(report.protected)

    def test_unapproved_directory_is_not_safe(self):
        manager = UninstallerManager()
        self.assertFalse(manager._safe_directory(Path.cwd()))


if __name__ == "__main__":
    unittest.main()
