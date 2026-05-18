# Architecture

**Status:** As-of pre-audit baseline. Expected to change during the deep dive refactor.

## Overview

Windows desktop autoclicker: Tkinter GUI, background click worker threads, settings persisted as JSON, automation via `pyautogui` / `mouse` / `keyboard`.

```
autoclicker.py          # Root shim: imports autoclicker.main:main
autoclicker/
  main.py               # Entry: AutoclickerApp().run()
  gui/main_window.py    # Tk UI, hotkeys, tray, status timer
  core/
    settings_manager.py # Load/save/validate autoclicker_settings.json
    click_engine.py     # Click loop and optional queue processor
    exceptions.py       # Typed errors and user-facing messages
  utils/
    coordinate_picker.py # Pick coordinates and named presets
```

## Threading model

| Thread / scheduler | Owner | Role |
|--------------------|-------|------|
| Main thread | Tkinter | UI event loop, `AutoclickerApp.run()` |
| Click thread | `ClickEngine.start_clicking` | Daemon thread running `_click_loop` |
| Queue processor | `ClickEngine` (optional) | Daemon thread when queuing enabled |
| Tray thread | `main_window.setup_system_tray` | Daemon thread running `pystray` icon |
| Status timer | Tk `root.after(1000, ...)` | Periodic status label updates |

All worker threads are daemon threads so process exit does not block on them.

## Data flow

1. **Settings:** `SettingsManager` reads/writes `autoclicker_settings.json` (path configurable via constructor).
2. **GUI:** `AutoclickerApp` binds Tk variables to settings, validates via `SettingsManager`, starts/stops clicking.
3. **Click engine:** Receives coordinates, interval, burst options, button type; calls `pyautogui` to click; invokes callbacks for status and completion.
4. **Screen input:** `CoordinatePicker` uses `mouse` hooks/listeners for pick mode; presets stored through `PresetManager` and settings.

## External dependencies

- `pyautogui`, `mouse`, `keyboard`: input automation
- `pywin32`: Windows integration (as pulled by stack)
- `Pillow`, `pystray`: tray icon
- `tkinter`: GUI (stdlib)

## Test layout

Unit tests live under `tests/` (pytest). `scripts/smoke_check.py` verifies imports and layout outside pytest.

## Deep-dive surface (map only)

Modules likely touched in a refactor or audit:

- `autoclicker/core/click_engine.py` - timing, safety, performance metrics, queue
- `autoclicker/core/settings_manager.py` - validation rules and persistence
- `autoclicker/core/exceptions.py` - error taxonomy and user messages
- `autoclicker/gui/main_window.py` - UI state, hotkeys, tray, click lifecycle
- `autoclicker/utils/coordinate_picker.py` - picker UX and presets
- Root `autoclicker.py` and packaging (`pyproject.toml`, PyInstaller CI job)

No behavioral recommendations here; see `audit/PRE_AUDIT_NOTES.md` for observed issues.
