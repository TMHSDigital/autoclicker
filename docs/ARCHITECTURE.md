# Architecture

## Overview

Windows desktop autoclicker: Tkinter GUI assembly, `AutoclickerController` for lifecycle, background click worker threads, settings in `%APPDATA%/WindowsAutoclicker/`, automation via `pyautogui` / `mouse` / `keyboard`.

```
autoclicker.py              # Root shim: imports autoclicker.main:main
autoclicker/
  main.py                   # Entry: AutoclickerApp().run()
  app/
    controller.py           # Settings, engine, picker, start/stop, session log
    hotkeys.py              # Global F6/F7/ESC registration
    tray.py                 # pystray icon
  gui/
    main_window.py          # Window shell, canvas, theme, wires sections + controller
    sections/               # Section builders: title, coordinates, click_settings,
                            #   advanced (collapsible), control, status bar, disclaimer
                            #   + collapsible.py (reusable disclosure frame)
  core/
    settings_manager.py     # Validation + JSON persistence
    settings_paths.py       # AppData path + legacy migration
    click_engine.py         # Click loop, queue, safety guards
    safety.py               # Failsafe + foreground window helpers
    session_log.py          # Append-only session log
    exceptions.py
  utils/
    coordinate_picker.py
```

## Threading model

| Thread / scheduler | Owner | Role |
|--------------------|-------|------|
| Main thread | Tkinter | UI event loop, `AutoclickerApp.run()` |
| Click thread | `ClickEngine.start_clicking` | Daemon thread running `_click_loop` |
| Queue processor | `ClickEngine` (optional) | Daemon thread when queuing enabled |
| Tray thread | `app.tray` | Daemon thread running `pystray` icon |
| Status timer | Tk `root.after(1000, ...)` | Periodic status label updates |

All worker threads are daemon threads so process exit does not block on them.

## Data flow

1. **Settings:** `SettingsManager` reads/writes `%APPDATA%/WindowsAutoclicker/autoclicker_settings.json` (legacy CWD file migrated once).
2. **GUI:** Sections bind Tk widgets; `AutoclickerController` validates and starts/stops clicking.
3. **Click engine:** Coordinates, interval, burst, safety limits; `pyautogui` with `PAUSE=0`; optional queue path.
4. **Session log:** Start/stop/safety events appended under AppData.
5. **Screen input:** `CoordinatePicker` uses `mouse` + ESC cancel; presets via `PresetManager`.

## External dependencies

- `pyautogui`, `mouse`, `keyboard`: input automation
- `pywin32`: foreground window check (`safety.py`)
- `Pillow`, `pystray`: tray icon
- `tkinter`: GUI (stdlib)
- `sv-ttk`: Sun Valley ttk theme (light/dark)

## Design decisions

- **GUI / logic split:** `AutoclickerController` (`app/controller.py`) owns settings, engine, picker, and presets; `gui/sections/*` only build widgets and forward values, keeping the UI replaceable without touching core logic.
- **Safety defaults:** PyAutoGUI failsafe is on by default, with a runaway clicks-per-second ceiling and an optional pause when the foreground window changes. All stops are recorded in the session log.
- **Performance:** O(1) Welford running stats back the 1 Hz status poll instead of recomputing aggregates over the timing history (see [PERFORMANCE.md](PERFORMANCE.md)). A Win32 `SendInput` hot path was evaluated and deferred (no measurable win over `pyautogui` with `PAUSE=0`, plus multi-monitor DPI risk).

## Test layout

Unit tests under `tests/` (pytest, 90 tests). Coverage gate on `autoclicker.core.click_engine`. `scripts/smoke_check.py` verifies imports outside pytest.
