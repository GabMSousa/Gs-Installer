from __future__ import annotations

from PySide6.QtWidgets import QApplication


def apply_theme(app: QApplication, theme: str) -> None:
    if theme == "light":
        app.setStyleSheet(LIGHT_QSS)
    else:
        app.setStyleSheet(DARK_QSS)


BASE = """
QWidget { font-family: 'Segoe UI'; font-size: 10pt; }
QMainWindow, QDialog { background: %s; color: %s; }
QFrame#rail, QFrame#panel { background: %s; border: 1px solid %s; border-radius: 12px; }
QLabel#brand { font-size: 17pt; font-weight: 700; letter-spacing: 1px; }
QLabel#eyebrow { color: %s; font-size: 9pt; font-weight: 600; }
QLabel#muted { color: %s; }
QPushButton { background: %s; color: %s; border: 1px solid %s; border-radius: 8px; padding: 8px 13px; }
QPushButton:hover { border-color: %s; }
QPushButton:pressed { background: %s; }
QPushButton#primary { background: %s; color: %s; border: none; font-weight: 700; }
QPushButton#danger { background: %s; color: %s; border: none; font-weight: 700; }
QLineEdit, QComboBox, QListWidget, QTreeWidget, QPlainTextEdit { background: %s; color: %s; border: 1px solid %s; border-radius: 8px; padding: 7px; selection-background-color: %s; }
QListWidget::item { padding: 8px 6px; border-bottom: 1px solid %s; }
QListWidget::item:selected { background: %s; color: %s; }
QCheckBox { spacing: 8px; padding: 6px 2px; }
QProgressBar { background: %s; border: 1px solid %s; border-radius: 5px; text-align: center; height: 10px; }
QProgressBar::chunk { background: %s; border-radius: 4px; }
QTabBar::tab { padding: 10px 14px; color: %s; }
QTabBar::tab:selected { color: %s; border-bottom: 2px solid %s; }
"""

DARK_QSS = BASE % ("#111417", "#F2EFE8", "#1A1F23", "#2D353B", "#E2A93B", "#8E9AA3", "#20262B", "#F2EFE8", "#3A444B", "#E2A93B", "#2A3035", "#E2A93B", "#111417", "#D95C5C", "#111417", "#1A1F23", "#F2EFE8", "#3A444B", "#766027", "#2D353B", "#303940", "#F2EFE8", "#20262B", "#3A444B", "#42B883", "#8E9AA3", "#F2EFE8", "#E2A93B")
LIGHT_QSS = BASE % ("#F2EFE8", "#20252A", "#FBFAF7", "#D7D1C6", "#A56F00", "#62707A", "#F7F4EC", "#20252A", "#C5BBAA", "#A56F00", "#E9E2D5", "#A56F00", "#FBFAF7", "#B12B2B", "#FBFAF7", "#FBFAF7", "#20252A", "#C5BBAA", "#D5B875", "#DDD6C9", "#20252A", "#F7F4EC", "#C5BBAA", "#18794E", "#62707A", "#20252A", "#A56F00", "#A56F00")
