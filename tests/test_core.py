from __future__ import annotations

import threading
import unittest
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory

from app.models import InstalledProgram, SoftwareItem
from app.data.catalog import local_catalog
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


class TestCatalog(unittest.TestCase):
    def test_local_catalog_discovers_exe_and_msi_recursively(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Navegadores").mkdir()
            (root / "Navegadores" / "ChromeSetup.exe").write_bytes(b"exe")
            (root / "Dev" / "Node").mkdir(parents=True)
            (root / "Dev" / "Node" / "node-v24.msi").write_bytes(b"msi")
            items = local_catalog(root)
            self.assertEqual(len(items), 2)
            self.assertTrue(all(item.local_path for item in items))
            self.assertEqual({item.category for item in items}, {"Navegadores", "Dev"})


class TestInstaller(unittest.TestCase):
    def test_force_reinstall_runs_even_when_detected_installed(self):
        with TemporaryDirectory() as directory:
            installer = Path(directory) / "DemoSetup.exe"
            installer.write_bytes(b"portable-test")
            item = SoftwareItem("demo", "Demo", "", "", local_path=str(installer))
            manager = InstallerManager(object(), Path(directory))
            manager.is_already_installed = lambda selected: True
            with patch("src.core.installer.subprocess.run") as run:
                run.return_value.returncode = 0
                result = manager.install_one(item, force_reinstall=True)
            self.assertEqual(result.status, InstallationStatus.SUCCESS)
            run.assert_called_once()

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
    def test_lists_all_supported_script_formats(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            scripts = root / "scripts"
            scripts.mkdir()
            (scripts / "cleanup.ps1").write_text("Write-Output 'test'", encoding="utf-8")
            (scripts / "cleanup.bat").write_text("@echo off", encoding="utf-8")
            (scripts / "cleanup.cmd").write_text("@echo off", encoding="utf-8")
            (scripts / "notes.txt").write_text("not executable", encoding="utf-8")
            manager = WinScriptManager(root / "cache", scripts)
            self.assertEqual({path.suffix for path in manager.list_scripts()}, {".ps1", ".bat", ".cmd"})

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
    def test_uninstall_many_reports_progress_for_each_program(self):
        manager = UninstallerManager()
        programs = [
            InstalledProgram("Windows Defender", "", "Microsoft", ""),
            InstalledProgram("Windows Security", "", "Microsoft", ""),
        ]
        progress = []
        reports = manager.uninstall_many(programs, deep=True, force=False, emit=lambda message: None, progress=lambda done, total: progress.append((done, total)))
        self.assertEqual(len(reports), 2)
        self.assertEqual(progress, [(1, 2), (2, 2)])

    def test_deep_scan_removes_files_and_directories_inside_approved_root(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            residual_dir = root / "DemoApp"
            residual_dir.mkdir()
            (residual_dir / "DemoApp.log").write_text("residual", encoding="utf-8")
            residual_file = root / "DemoApp.cache"
            residual_file.write_text("residual", encoding="utf-8")
            manager = UninstallerManager()
            program = InstalledProgram("Demo App", "", "", "", install_location=str(residual_dir))
            with patch.object(UninstallerManager, "_approved_roots", classmethod(lambda cls: [root.resolve()])):
                candidates = manager.scan_file_residuals(program)
                removed = manager.remove_file_residuals(candidates, lambda message: None)
            self.assertTrue(removed)
            self.assertFalse(residual_dir.exists())
            self.assertFalse(residual_file.exists())

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
