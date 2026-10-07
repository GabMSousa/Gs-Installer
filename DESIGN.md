# GS Installer — Visual system

## Direction

Operational field instrument: a portable technician's bench with a dark graphite work surface, a quiet bone light theme, hairline measurement rules, and amber actions. The first viewport shows the task, selection state, and live activity together.

## First viewport

The left rail names the three jobs: Install, Clean, Uninstall. The workbench opens on Install with the catalog search, category filter, selection count, and a visible activity ledger. Empty and offline states explain the next action instead of becoming decorative blanks.

## Interaction

Selections are keyboard reachable, persist in JSON, and use the same checkbox model in install and cleanup. Primary actions are protected by explicit confirmation when they affect the system. Progress is reported in the activity ledger and written to disk.

## Tokens

- Graphite `#111417`, graphite raised `#1A1F23`, bone `#F2EFE8`, bone raised `#FBFAF7`
- Amber action `#E2A93B`, green success `#42B883`, red danger `#D95C5C`, slate text `#8E9AA3`
- Hairline rules, 8px base rhythm, 10–14px radii, no gradients, no emoji icons
- UI type uses Segoe UI; data and logs use Cascadia Mono when available
- Focus is a 2px amber ring; status never depends on color alone

## Raises

- Reference-setting discipline: dense content is organized by category rails and stable alignment, not nested cards.
- Wayfinding discipline: actions make the route through install, clean, and uninstall obvious and preserve context while the work changes.
- Data-sublime discipline: logs and progress use high-signal tabular rows and deliberate state changes while remaining readable.

## Quality bar

The shipped UI must support keyboard navigation, both themes, loading/error/empty states, real copy, confirmation for destructive work, and a narrow layout that keeps the primary action reachable.
