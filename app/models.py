from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SoftwareItem:
    slug: str
    name: str
    category: str
    official_url: str
    silent_args: tuple[str, ...] = ("/S", "/quiet", "/silent", "/verysilent")
    github_repo: str | None = None


@dataclass
class InstalledProgram:
    name: str
    version: str
    publisher: str
    uninstall_string: str
    install_location: str = ""
    registry_key: str = ""
    quiet_uninstall_string: str = ""
    size_kb: int | None = None
    registry_hive: str = ""
