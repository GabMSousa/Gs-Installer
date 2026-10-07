from __future__ import annotations

from PySide6.QtWidgets import QApplication


def apply_theme(app: QApplication, theme: str = "dark") -> None:
    # The product is intentionally a black/red operator console. ``light`` is
    # kept as a compatibility value, but never changes the accent color.
    app.setStyleSheet(DARK_QSS if theme != "light" else LIGHT_QSS)


COMMON = """
QWidget { font-family: 'Segoe UI'; font-size: 10pt; color: #F3F4F6; }
QMainWindow, QDialog { background: #080A0D; color: #F3F4F6; }
QFrame#rail { background: #0D1014; border-right: 1px solid #242A31; }
QFrame#panel, QFrame#stat { background: #11151A; border: 1px solid #252D35; border-radius: 12px; }
QLabel#brand { font-size: 18pt; font-weight: 800; color: #FFFFFF; letter-spacing: 1px; }
QLabel#brandMark { color: #E53935; font-size: 22pt; font-weight: 900; }
QLabel#eyebrow { color: #E66B68; font-size: 8pt; font-weight: 700; letter-spacing: 1px; }
QLabel#muted { color: #9BA4AE; }
QLabel#metric { color: #FFFFFF; font-size: 16pt; font-weight: 800; }
QLabel#metricLabel { color: #AAB2BB; font-size: 8pt; font-weight: 700; letter-spacing: .5px; }
QPushButton { background: #151A20; color: #E8EAED; border: 1px solid #2C353F; border-radius: 8px; padding: 9px 13px; }
QPushButton:hover { background: #1D232A; border-color: #E53935; }
QPushButton:pressed { background: #2A1718; }
QPushButton:disabled { color: #5E6872; border-color: #20262D; }
QPushButton#primary, QPushButton#danger { background: #C62828; color: #FFFFFF; border: 1px solid #E53935; font-weight: 800; }
QPushButton#primary:hover, QPushButton#danger:hover { background: #E53935; }
QPushButton#primary:pressed, QPushButton#danger:pressed { background: #8E1B1B; }
QPushButton#nav { text-align: left; padding: 11px 13px; background: transparent; border: 1px solid transparent; color: #AEB6BF; font-weight: 600; }
QPushButton#nav:hover { background: #171C22; color: #FFFFFF; }
QPushButton#nav[active="true"] { background: #321517; border: 1px solid #6D2527; color: #FFFFFF; }
QLineEdit, QComboBox, QListWidget, QTreeWidget, QPlainTextEdit { background: #0E1216; color: #F3F4F6; border: 1px solid #29323B; border-radius: 8px; padding: 8px; selection-background-color: #7F2022; }
QLineEdit:focus, QComboBox:focus, QListWidget:focus, QPlainTextEdit:focus { border: 1px solid #E53935; }
QComboBox QAbstractItemView { background: #11151A; color: #FFFFFF; border: 1px solid #3A444F; selection-background-color: #7F2022; }
QListWidget { padding: 6px; outline: none; }
QListWidget::item { background: #12171D; border: 1px solid #27313A; border-radius: 10px; padding: 14px; margin: 6px; }
QListWidget::item:hover { background: #191F26; border-color: #8B2B2D; }
QListWidget::item:selected { background: #321517; border: 1px solid #E53935; color: #FFFFFF; }
QCheckBox { spacing: 10px; padding: 8px 4px; }
QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px; border: 1px solid #68727D; background: #0D1115; }
QCheckBox::indicator:hover { border-color: #E53935; }
QCheckBox::indicator:checked { background: #E53935; border-color: #E53935; }
QProgressBar { background: #151B21; border: 1px solid #29323B; border-radius: 5px; text-align: center; height: 12px; color: #FFFFFF; }
QProgressBar::chunk { background: #E53935; border-radius: 4px; }
QTabWidget::pane { border: 0; }
QTabBar { height: 0px; }
QSplitter::handle { background: #252D35; }
QScrollBar:vertical { background: #0B0E11; width: 12px; margin: 3px; }
QScrollBar::handle:vertical { background: #3A444F; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #E53935; }
QToolTip { background: #161B21; color: #FFFFFF; border: 1px solid #E53935; padding: 5px; }
"""

DARK_QSS = COMMON

LIGHT_QSS = COMMON + """
QMainWindow, QDialog { background: #F5F6F7; color: #17191D; }
QWidget { color: #17191D; }
QFrame#rail { background: #FFFFFF; border-right: 1px solid #D6DCE2; }
QFrame#panel, QFrame#stat { background: #FFFFFF; border-color: #D6DCE2; }
QLabel#brand, QLabel#metric { color: #17191D; }
QLabel#muted, QLabel#metricLabel { color: #5B6570; }
QPushButton { background: #FFFFFF; color: #2B3138; border-color: #CDD4DB; }
QPushButton:hover { background: #FFF4F4; }
QLineEdit, QComboBox, QListWidget, QTreeWidget, QPlainTextEdit { background: #FFFFFF; color: #17191D; border-color: #CDD4DB; }
QListWidget::item { background: #FFFFFF; border-color: #D6DCE2; }
QListWidget::item:hover { background: #FFF5F5; }
QListWidget::item:selected { background: #FFE9E9; color: #17191D; }
QProgressBar { background: #E8ECF0; color: #17191D; }
"""
