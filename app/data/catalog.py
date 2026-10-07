from __future__ import annotations

import re
from pathlib import Path

from app.models import SoftwareItem


def _item(slug: str, name: str, category: str, url: str, repo: str | None = None) -> SoftwareItem:
    return SoftwareItem(slug, name, category, url, github_repo=repo)


CATALOG = [
    _item("chrome", "Google Chrome", "Navegadores", "https://www.google.com/chrome/"),
    _item("firefox", "Mozilla Firefox", "Navegadores", "https://www.mozilla.org/firefox/download/"),
    _item("edge", "Microsoft Edge", "Navegadores", "https://www.microsoft.com/edge"),
    _item("brave", "Brave", "Navegadores", "https://brave.com/download/"),
    _item("opera", "Opera", "Navegadores", "https://www.opera.com/download"),
    _item("vivaldi", "Vivaldi", "Navegadores", "https://vivaldi.com/download/"),
    _item("discord", "Discord", "Mensageria", "https://discord.com/download"),
    _item("telegram", "Telegram", "Mensageria", "https://desktop.telegram.org/"),
    _item("whatsapp", "WhatsApp", "Mensageria", "https://www.whatsapp.com/download"),
    _item("slack", "Slack", "Mensageria", "https://slack.com/downloads"),
    _item("zoom", "Zoom", "Mensageria", "https://zoom.us/download"),
    _item("teams", "Microsoft Teams", "Mensageria", "https://www.microsoft.com/microsoft-teams/download-app"),
    _item("vlc", "VLC", "Mídia", "https://www.videolan.org/vlc/"),
    _item("spotify", "Spotify", "Mídia", "https://www.spotify.com/download"),
    _item("audacity", "Audacity", "Mídia", "https://www.audacityteam.org/download/"),
    _item("obs", "OBS Studio", "Mídia", "https://obsproject.com/download", "obsproject/obs-studio"),
    _item("handbrake", "HandBrake", "Mídia", "https://handbrake.fr/downloads.php"),
    _item("foobar2000", "foobar2000", "Mídia", "https://www.foobar2000.org/download"),
    _item("7zip", "7-Zip", "Utilitários", "https://www.7-zip.org/download.html"),
    _item("notepadpp", "Notepad++", "Utilitários", "https://notepad-plus-plus.org/downloads/", "notepad-plus-plus/notepad-plus-plus"),
    _item("everything", "Everything", "Utilitários", "https://www.voidtools.com/"),
    _item("powertoys", "PowerToys", "Utilitários", "https://github.com/microsoft/PowerToys/releases", "microsoft/PowerToys"),
    _item("sharex", "ShareX", "Utilitários", "https://getsharex.com/", "ShareX/ShareX"),
    _item("treesize", "TreeSize Free", "Utilitários", "https://www.jam-software.com/treesize_free"),
    _item("python", "Python", "Desenvolvimento", "https://www.python.org/downloads/"),
    _item("nodejs", "Node.js", "Desenvolvimento", "https://nodejs.org/"),
    _item("git", "Git", "Desenvolvimento", "https://git-scm.com/download/win"),
    _item("vscode", "VS Code", "Desenvolvimento", "https://code.visualstudio.com/download"),
    _item("sublime", "Sublime Text", "Desenvolvimento", "https://www.sublimetext.com/download"),
    _item("filezilla", "FileZilla", "Desenvolvimento", "https://filezilla-project.org/download.php?platform=win64"),
    _item("malwarebytes", "Malwarebytes", "Segurança / Limpeza", "https://www.malwarebytes.com/"),
    _item("winscript", "WinScript", "Segurança / Limpeza", "https://github.com/flick9000/winscript", "flick9000/winscript"),
    _item("steam", "Steam", "Outros", "https://store.steampowered.com/about/"),
    _item("qbittorrent", "qBittorrent", "Outros", "https://www.qbittorrent.org/download", "qbittorrent/qBittorrent"),
    _item("winrar", "WinRAR", "Outros", "https://www.win-rar.com/download.html"),
]


def local_catalog(installer_dir: Path | str) -> list[SoftwareItem]:
    """Expose every local EXE/MSI as a selectable catalog item."""
    root = Path(installer_dir)
    if not root.exists():
        return []
    items: list[SoftwareItem] = []
    seen: set[str] = set()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.casefold() not in {".exe", ".msi"}:
            continue
        relative = path.relative_to(root)
        category = relative.parts[0] if len(relative.parts) > 1 else "Instaladores locais"
        name = re.sub(r"[_-]+", " ", path.stem).strip()
        name = re.sub(r"\s+", " ", name)
        slug = re.sub(r"[^a-z0-9]+", "", name.casefold()) or "local"
        base_slug = slug
        suffix = 2
        while slug in seen or any(item.slug == slug for item in CATALOG):
            slug = f"{base_slug}{suffix}"
            suffix += 1
        seen.add(slug)
        items.append(SoftwareItem(slug, name, category, "", local_path=str(path)))
    return items


def build_catalog(installer_dir: Path | str) -> list[SoftwareItem]:
    """Return the official catalog followed by all local installer files."""
    return [*CATALOG, *local_catalog(installer_dir)]
