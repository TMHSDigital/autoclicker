# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- UI/UX refresh: modern Sun Valley (`sv-ttk`) theme with light/dark toggle (persisted via new `theme` setting) and Segoe UI typography.
- Simplified default view: burst mode, safety limits, and advanced toggles moved into a collapsible "Advanced" section (collapsed by default).
- Status panel reworked into a compact status bar with a colored state indicator and inline metrics.
- Disclaimer reduced to a one-line footer with an info dialog; removed the always-on horizontal scrollbar.

### Added

- `sv-ttk` dependency for theming.
- Reusable `CollapsibleFrame` (`gui/sections/collapsible.py`) and `gui/sections/advanced.py`.
- "Limit clicks" toggle in the Advanced section; when off, the click count is unlimited (runs indefinitely).
- System tray now uses the real app icon (`autoclicker.png`/`.ico`) with a solid-color fallback.

## [1.2.0] - 2026-05-19

### Added

- Deep-dive audit and regression tests for queue, picker, and settings edge cases.
- Click engine unit tests with 88%+ line coverage and pytest `cov-fail-under` gate.
- Welford running timing stats for O(1) status polling (see [docs/PERFORMANCE.md](docs/PERFORMANCE.md)).
- Configurable PyAutoGUI failsafe (default on), runaway CPS guard, optional pause when unfocused.
- Session log at `%APPDATA%/WindowsAutoclicker/sessions.log`.
- AppData settings path with one-time CWD legacy migration (`.migrated` marker beside legacy file).
- `AutoclickerController`, `app/hotkeys`, `app/tray`, and `gui/sections/` layout.

### Fixed

- Click queue counter and processor re-queue bugs.
- Settings validation on non-numeric strings and invalid `interval_unit`.
- Exception `.reason` / `details` contract; coordinate validation tests.
- Coordinate picker hook handle + ESC cancel; quit persists UI settings.
- Hotkey/tray errors surface in the status bar.

### Changed

- CI: unit tests and coverage are required (no `continue-on-error` on test steps).
- Ruff/mypy: removed blanket production ignores; narrowed per-module rules.

## [1.1.0] - Baseline

Baseline release prior to the structured audit and refactor pass.

[Unreleased]: https://github.com/TMHSDigital/autoclicker/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/TMHSDigital/autoclicker/releases/tag/v1.2.0
[1.1.0]: https://github.com/TMHSDigital/autoclicker/releases/tag/v1.1.0
