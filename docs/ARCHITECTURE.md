# Architecture

## Overview

Windows desktop autoclicker: Tkinter GUI assembly, `AutoclickerController` for lifecycle, background click worker threads, settings in `%APPDATA%/WindowsAutoclicker/`, clicking via `pyautogui`, global hotkeys via Win32 `RegisterHotKey`.

```
autoclicker.py              # Root shim: imports autoclicker.main:main
autoclicker/
  main.py                   # Entry: logging setup, AutoclickerApp().run()
  app/
    controller.py           # Settings, engine, picker, start/stop, session log
    hotkeys.py              # RegisterHotKey thread; claims keys by run state
    tray.py                 # pystray icon
  gui/
    main_window.py          # Window shell; marshals worker callbacks via root.after
    sections/               # Section builders: title, coordinates, click_settings,
                            #   advanced (collapsible), control, status bar, disclaimer
                            #   + collapsible.py (reusable disclosure frame)
  core/
    settings_manager.py     # Validation + atomic JSON persistence
    settings_paths.py       # AppData path + legacy migration
    click_engine.py         # Click loop, safety guards
    safety.py               # Failsafe + fail-closed foreground window helpers
    session_log.py          # Session events, rotated at 1 MB
    single_instance.py      # Named mutex + show event: one running instance
    app_data.py             # %APPDATA%/WindowsAutoclicker (never CWD-relative)
    screen.py               # Virtual-desktop bounds across monitors
    resources.py            # Frozen/source asset paths
    logging_setup.py        # stderr + AppData rotating log
    exceptions.py
  utils/
    coordinate_picker.py
```

## Threading model

| Thread / scheduler | Owner | Role |
|--------------------|-------|------|
| Main thread | Tkinter | UI event loop, `AutoclickerApp.run()` |
| Click thread | `ClickEngine.start_clicking` | Daemon thread running `_click_loop` |
| Hotkey thread | `app.hotkeys.HotkeyManager` | Daemon thread owning `RegisterHotKey` and its message loop |
| Tray thread | `app.tray` | Daemon thread running `pystray` icon |
| Status timer | Tk `root.after(1000, ...)` | Periodic status label updates |

All worker threads are daemon threads so process exit does not block on them.

Worker callbacks (hotkeys, tray, run finished) are marshaled onto the Tk thread with `root.after(0, ...)`. The click thread never `join()`s itself.

Hotkeys use `RegisterHotKey`, which delivers a key only to this app. To avoid taking keys away from other programs, `HotkeyManager` claims the Start (and optional toggle) key while idle and the Stop and Emergency keys only while clicking; the GUI calls `set_running` when a run starts and ends. Bindings live in the `hotkeys` setting and are edited in the Hotkeys dialog, which suspends all keys while it is open.

## Stop paths

| Path | Stop reason (`RunOutcome.reason`) | Clears `is_running` | Joins click thread |
|------|-----------------------------------|---------------------|--------------------|
| `stop_clicking` | `user_stop` | yes | yes, if not the click thread |
| `emergency_stop` | `emergency` | yes | no |
| runaway / failsafe | `safety` | yes (click thread) | UI reaps via `finish_run` |
| max_clicks / auto_stop | `completed` | yes (`finally`) | UI reaps via `finish_run` |
| exception in the loop | `error` (carries the exception) | yes (`finally`) | UI reaps via `finish_run` |

The first stop source to fire records the reason; later ones are ignored. The click thread's `finally` builds one `RunOutcome` and calls `on_finished` exactly once per run. The controller writes the single `stop` session-log line from that callback (on the click thread, so it is written even during quit), then the GUI marshals it to the Tk thread to paint the status and, for `error`, show a dialog.

Clicks are only ever issued from the click thread, so once a stop call returns (or, for `emergency_stop`, once the click thread exits) no further clicks happen.

## Data flow

1. **Settings:** `SettingsManager` atomically writes `%APPDATA%/WindowsAutoclicker/autoclicker_settings.json` (legacy CWD file migrated once).
2. **GUI:** Sections bind Tk widgets; `AutoclickerController` validates and starts/stops clicking.
3. **Click engine:** Coordinates, interval, burst, safety limits; `pyautogui` with `PAUSE=0`. Waits use `_stop_event.wait`.
4. **Session log:** Start/stop/safety events appended under AppData.
5. **Pick Location:** `gui/picker.py` shows a borderless, topmost, translucent Tk overlay over the whole virtual desktop. The pick click lands on the overlay (never on the app underneath); Esc or right-click cancels. It runs entirely on the Tk thread. Presets live in `utils/coordinate_picker.py` (`PresetManager`).

## External dependencies

- `pyautogui`: cursor movement and clicks
- Win32 `RegisterHotKey` (ctypes, `app/hotkeys.py`): global hotkeys without a keyboard hook
- `pywin32`: foreground window check (`safety.py`)
- `Pillow`, `pystray`: tray icon
- `tkinter`: GUI (stdlib)
- `sv-ttk`: Sun Valley ttk theme (light/dark)

## Design decisions

- **GUI / logic split:** `AutoclickerController` (`app/controller.py`) owns settings, engine, picker, and presets; `gui/sections/*` only build widgets and forward values, keeping the UI replaceable without touching core logic.
- **Safety defaults:** PyAutoGUI failsafe is on by default, with a runaway clicks-per-second ceiling and an optional pause when the foreground window changes (fail-closed if the HWND cannot be read). All stops are recorded in the session log.
- **Performance:** O(1) Welford running stats back the 1 Hz status poll instead of recomputing aggregates over the timing history (see [PERFORMANCE.md](PERFORMANCE.md)). A Win32 `SendInput` hot path was evaluated and deferred (no measurable win over `pyautogui` with `PAUSE=0`, plus multi-monitor DPI risk).

## Test layout

Unit tests under `tests/` (pytest). Coverage gate on the `autoclicker` package (`cov-fail-under=65`, `gui/sections` omitted). `scripts/smoke_check.py` verifies imports outside pytest and runs in CI on Python 3.11.
