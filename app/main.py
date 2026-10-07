from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.core.config import AppConfig
from app.core.logging_config import configure_logging
from app.ui.main_window import MainWindow


def main() -> int:
    config = AppConfig.load()
    configure_logging(config.paths.logs)
    app = QApplication(sys.argv)
    app.setApplicationName("GS Installer")
    app.setOrganizationName("GS Installer")
    window = MainWindow(config)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
