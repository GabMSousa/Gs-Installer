from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont

ICON_DIR = Path(__file__).resolve().parents[1] / "assets" / "icons"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _fallback(text: str) -> QIcon:
    pixmap = QPixmap(48, 48)
    pixmap.fill(QColor("#20262D"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor("#E53935"))
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


def icon_size(size: int = 42) -> QSize:
    return QSize(size, size)
