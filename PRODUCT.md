# Product

<!-- impeccable:product-schema 1 -->

## Platform

windows

## Stack

delegated: Python 3.11+ with PySide6 and PyInstaller, chosen for a native-feeling Windows desktop interface, maintainability, and a single portable executable.

## Users

Technicians and power users who prepare or maintain Windows 10/11 machines and need to install a repeatable set of applications, run trusted cleanup routines, or remove software in batches.

## Product Purpose

GS Installer is a portable Windows utility that centralizes bulk application installation, WinScript-based cleanup, and deep software removal. Success means a technician can complete those jobs with visible progress, recoverable logs, offline cache support, and explicit confirmation before system-impacting actions.

## Positioning

One local, portable workflow combines a configurable official-source application catalog, offline-capable cleanup scripts, and auditable uninstall residual scanning without requiring a pre-installed runtime.

## Operating Context

The application runs from a writable portable folder, may be launched as administrator for system operations, and uses local installer/cache/script/log folders. It must keep working when the configured installer folder is empty by using official download sources when available.

## Capabilities and Constraints

- Installer catalog grouped by the README categories, with multi-selection, search, profiles, local-cache lookup, official-source download, silent execution, progress, and logs.
- Cleanup tab with WinScript repository acquisition, offline script cache, preview, multi-selection, explicit confirmation, and execution logs.
- Uninstaller tab that reads Windows uninstall registry entries, invokes an official uninstaller when present, scans likely residual paths and registry keys, supports forced removal only after confirmation, and produces a report.
- Preferences include installer path, theme, last selections, and portable storage paths; configuration is JSON and does not depend on application registry settings.
- Security-sensitive operations must disclose limitations, prefer official sources, verify SHA-256 when metadata is available, and never silently delete residuals.
- Optional provider data is allowed to be incomplete when an official site exposes a landing page rather than a stable direct installer URL; the UI must say what action is available.

## Brand Commitments

The product name is GS Installer. The README requires a professional Windows utility with dark and light themes, clear progress, detailed logs, and a Ninite-like selection experience.

## Evidence on Hand

The authoritative brief is `Readme.md`. No supplied logo, screenshots, installer binaries, or validated third-party script bundle are present yet. Do not fabricate vendor claims or checksums.

## Product Principles

1. Make system-changing work inspectable before it runs.
2. Prefer official sources and honest capability states over hidden fallbacks.
3. Keep the portable folder self-contained and useful offline after first acquisition.
4. Make repeated technician workflows fast through search, profiles, and batch selection.
5. Preserve an audit trail in human-readable logs and reports.

## Accessibility & Inclusion

Support keyboard navigation, visible focus, high-contrast readable text in both themes, scalable layouts, and status messages that do not rely on color alone.
