from __future__ import annotations

import re
import os
from pathlib import Path

from PySide6.QtCore import QSize, QFileInfo
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QBrush
from PySide6.QtWidgets import QFileIconProvider

ICON_DIR = Path(__file__).resolve().parents[1] / "assets" / "icons"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


BRAND_COLORS = {
    "chrome": "#EA4335", "firefox": "#FF7139", "edge": "#0A84FF", "brave": "#FB542B",
    "discord": "#5865F2", "telegram": "#26A5E4", "whatsapp": "#25D366", "zoom": "#2D8CFF",
    "vlc": "#FF8800", "spotify": "#1DB954", "python": "#3776AB", "nodejs": "#339933",
    "vscode": "#007ACC", "steam": "#1B2838", "git": "#F05032", "7zip": "#111111",
}


def _fallback(text: str) -> QIcon:
    pixmap = QPixmap(48, 48)
    token = _slug(text)
    color = BRAND_COLORS.get(token, "#3A4652")
    pixmap.fill(QColor("#11151A"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QBrush(QColor(color)))
    painter.setPen(QColor(color))
    painter.drawRoundedRect(3, 3, 42, 42, 10, 10)
    painter.setPen(QColor("#FFFFFF"))
    painter.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
    painter.drawText(pixmap.rect(), 0x84, (text or "GS")[:2].upper())
    painter.end()
    return QIcon(pixmap)


def icon_for(value: str, size: int = 42) -> QIcon:
    token = _slug(value)
    aliases = {
        "googlechrome": "chrome", "microsoftedge": "edge", "microsoftteams": "teams",
        "visualstudiocode": "vscode", "7zip": "7zip", "notepad": "notepadpp",
        "obsstudio": "obs", "treesizefree": "treesize", "nodejs": "nodejs",
    }
    filename = aliases.get(token, token) + ".svg"
    candidate = ICON_DIR / filename
    if candidate.exists():
        icon = QIcon(str(candidate))
        if not icon.isNull():
            return icon
    return _fallback(value)


def icon_for_installed(display_icon: str, name: str) -> QIcon:
    """Prefer the real executable/icon registered by Windows for uninstall rows."""
    if display_icon:
        raw_path = display_icon.split(",", 1)[0].strip('"')
        path = Path(os.path.expandvars(raw_path)).expanduser()
        if path.exists() and path.is_file():
            icon = QFileIconProvider().icon(QFileInfo(str(path)))
            if not icon.isNull():
                return icon
    return icon_for(name)


def icon_size(size: int = 42) -> QSize:
    return QSize(size, size)
