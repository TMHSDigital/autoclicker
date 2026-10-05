# Architecture

## Overview

Windows desktop autoclicker: Tkinter GUI assembly, `AutoclickerController` for lifecycle, background click worker threads, settings in `%APPDATA%/WindowsAutoclicker/`, clicking via `pyautogui`, global hotkeys via Win32 `RegisterHotKey`.

```
autoclicker.py              # Root shim: imports autoclicker.main:main
autoclicker/
  main.py                   # Entry: DPI, logging, single instance, CLI or AutoclickerApp().run()
  cli.py                    # Command-line flags -> profile-shaped overrides; --headless run
  app/
    controller.py           # Settings, engine, start/stop, image target loading, session log
    hotkeys.py              # RegisterHotKey thread; claims keys by run state
    tray.py                 # pystray icon
  gui/
    main_window.py          # Window shell, start/stop, settings lock; marshals worker callbacks
    features/               # Feature mixins: sequence, recording, image, profiles, condition,
                            #   countdown, updates, info; base.py declares shared widgets
    sections/               # Section builders: title, coordinates, click_settings,
                            #   advanced (collapsible), control, status bar, disclaimer
                            #   + collapsible.py (reusable disclosure frame)
    picker.py               # Full-desktop overlay: pick a point or drag an area
    dialogs.py              # messagebox/simpledialog/filedialog, patched in one place by tests
    hotkeys_dialog.py       # Rebind hotkeys (suspends all global keys while open)
    info_dialog.py          # About + Copy diagnostics
    styles.py               # Theme-aware Muted/Error label styles (WCAG AA)
  core/
    settings_manager.py     # Parsing, validation, mode/action rules, atomic JSON persistence
    settings_paths.py       # AppData path + one-time legacy migration from next to the app
    click_engine.py         # Click loop, sequences, hold/key, pixel and image watchers, safety
    image_match.py          # Exact template search in a screen region; captured image storage
    recorder.py             # WH_MOUSE_LL hook, installed only while recording a sequence
    safety.py               # Failsafe + fail-closed foreground window helpers
    session_log.py          # Session events, rotated at 1 MB
    single_instance.py      # Named mutex + show event: one running instance
    app_data.py             # %APPDATA%/WindowsAutoclicker (never CWD-relative)
    dpi.py                  # Per-monitor DPI awareness, set before PyAutoGUI loads
    screen.py               # Virtual-desktop bounds, monitor corners, cursor position
    diagnostics.py          # Copy diagnostics report (personal details summarized)
    updates.py              # Opt-in daily check of the latest GitHub release
    resources.py            # Asset paths (autoclicker/assets) for source, wheel and frozen runs
    logging_setup.py        # stderr + AppData rotating log
    exceptions.py
  utils/
    profiles.py             # PresetManager: named profiles, import/export (embedded images)
    coordinate_picker.py    # Deprecated alias of profiles.py (renamed in 1.6.0)
```

## Threading model

| Thread / scheduler | Owner | Role |
|--------------------|-------|------|
| Main thread | Tkinter | UI event loop, `AutoclickerApp.run()` |
| Click thread | `ClickEngine.start_clicking` | Daemon thread running `_click_loop` |
| Hotkey thread | `app.hotkeys.HotkeyManager` | Daemon thread owning `RegisterHotKey` and its message loop |
| Tray thread | `app.tray` | Daemon thread running `pystray` icon |
| Status timer | Tk `root.after(1000, ...)` | Periodic status label updates |
| Pixel watcher | `PixelWatch` daemon thread | Polls the watched pixel during a run with a pixel condition |
| Image watcher | `ImageWatch` daemon thread | Searches for the captured image every 100 ms during an image-target run |
| Recorder hook | `ClickRecorder` daemon thread | Owns the `WH_MOUSE_LL` hook and its message loop, only while recording |
| Update check | `UpdateCheck` daemon thread | One GET of the latest-release API, at most daily, when enabled |
| Single instance | `SingleInstanceWatch` daemon thread | Waits for a second launch's "show yourself" event |

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

In sequence mode (`ClickEngine.start_clicking(..., steps=[ClickStep, ...], repeat=N)`) each round calls `_perform_sequence`, which re-checks stop requests, limits, pause when unfocused and the runaway guard before every step and waits each step's `delay_ms` with `_stop_event.wait`. The round's last step is followed by the normal interval. Errors name the step (`Step 2: ...`).

With a pixel condition, a `PixelWatch` daemon thread (tagged with the run id, so a stale one exits) keeps `_condition_state` current; before each burst and each sequence step `_check_condition` returns go, wait (shown as Paused with `pause_reason`) or stop. No reading yet counts as wait.

With an image target, an `ImageWatch` daemon thread (also tagged with the run id) stores `(position or None, time the search began)` in `_image_match`. The click loop waits (Paused, `PAUSE_IMAGE`) while nothing is found, and clicks a match only if its search began at least `_IMAGE_SETTLE_SECONDS` after the previous click, so a click that closes the image is never repeated on whatever is underneath. `image_region` stores where the image was captured; the controller grows it by `image_margin` (clipped to the desktop) when the run starts. Twenty failed grabs in a row end the run with `error`; a search that simply finds nothing is not a failure.

Recording (`gui/features/recording.py`, `core/recorder.py`) is not a run: no click thread exists. The hook thread posts each press through `_ui` to the Tk thread, which drops clicks on the app's own windows. The Stop and Emergency keys are claimed while recording and finish it, and Start is refused until it ends.

While a countdown or run is in progress `AutoclickerApp._set_settings_locked` disables the controls in the scrolling settings frame (section headers stay usable), and `_paint_stopped` restores exactly the ones it disabled. Settings changed mid-run would not reach the engine.

A Start-button or tray start first runs a countdown on the Tk thread (`root.after(1000, ...)`, `start_delay_seconds`). No click thread exists yet, so Stop, Emergency stop and the toggle key just cancel the pending `after` job; nothing is logged because no run started.

The first stop source to fire records the reason; later ones are ignored. The click thread's `finally` builds one `RunOutcome` and calls `on_finished` exactly once per run. The controller writes the single `stop` session-log line from that callback (on the click thread, so it is written even during quit), then the GUI marshals it to the Tk thread to paint the status and, for `error`, show a dialog.

Clicks are only ever issued from the click thread, so once a stop call returns (or, for `emergency_stop`, once the click thread exits) no further clicks happen.

## Data flow

1. **Settings:** `SettingsManager` atomically writes `%APPDATA%/WindowsAutoclicker/autoclicker_settings.json` (a legacy file next to the app, not the working folder, is migrated once).
2. **GUI:** Sections bind Tk widgets; `AutoclickerController` validates and starts/stops clicking.
3. **Click engine:** Coordinates, interval, burst, safety limits; `pyautogui` with `PAUSE=0`. Waits use `_stop_event.wait`.
4. **Session log:** Start/stop/safety events appended under AppData.
5. **Pick Location:** `gui/picker.py` shows a borderless, topmost, translucent Tk overlay over the whole virtual desktop. The pick click lands on the overlay (never on the app underneath); Esc or right-click cancels. It runs entirely on the Tk thread. Image capture uses the same overlay in area mode (drag a rectangle). Profiles (stored under the `presets` setting) live in `utils/profiles.py` (`PresetManager`), including JSON import/export; an image profile's PNG travels inside the export as base64 and is re-encoded into `%APPDATA%/WindowsAutoclicker/images/` on import, never as a path.
6. **Mode rules:** `settings_manager.allowed_actions(mode)` and `uses_point(mode, action)` are the one definition of which actions and fields each target mode uses; validation, the controller and the form all call them.

## External dependencies

- `pyautogui`: cursor movement and clicks
- Win32 `RegisterHotKey` (ctypes, `app/hotkeys.py`): global hotkeys without a keyboard hook
- `pywin32`: foreground window check (`safety.py`)
- `Pillow`: screen grabs and template matching for image targets, the tray image
- `pystray`: tray icon
- `tkinter`: GUI (stdlib)
- `sv-ttk`: Sun Valley ttk theme (light/dark)

## Design decisions

- **GUI features:** `gui/main_window.py` keeps window setup, start/stop, hotkeys, tray and the status line. Each feature's handlers live in a mixin under `gui/features/` (sequence, recording, image, profiles, condition, countdown, updates, info); `features/base.py` declares the shared widgets and cross-feature methods so every module type-checks on its own. Standard dialogs are reached through `gui/dialogs.py` so tests patch them in one place.
- **GUI / logic split:** `AutoclickerController` (`app/controller.py`) owns settings, engine, picker, and presets; `gui/sections/*` only build widgets and forward values, keeping the UI replaceable without touching core logic.
- **Command line:** `cli.py` parses flags into profile-shaped overrides. In GUI mode `main.py` applies them with `AutoclickerApp.apply_form_values` and can schedule `start_from_button`; `--headless` runs `cli.run_headless`, which validates through the controller, starts with `persist=False`, registers the hotkeys without a window and maps the `RunOutcome` reason to an exit code.
- **DPI:** `main.py` opts the process into per-monitor-v2 DPI awareness (`core/dpi.py`) before PyAutoGUI is imported, so Tk events, `GetCursorPos`, monitor rectangles and clicks all use physical pixels on every monitor. Verified on a single-DPI two-monitor desktop; mixed-DPI (for example 150% next to 100%) still needs a manual pick-and-click check (#67).
- **Safety defaults:** the corner failsafe is on by default and covers every monitor (the engine checks `GetCursorPos` against the outer corners from `screen.failsafe_corners` before each click; PyAutoGUI's primary-monitor check stays as a backstop), with a runaway clicks-per-second ceiling and an optional pause when the foreground window changes (fail-closed if the HWND cannot be read). All stops are recorded in the session log.
- **Performance:** O(1) Welford running stats back the 1 Hz status poll instead of recomputing aggregates over the timing history (see [PERFORMANCE.md](PERFORMANCE.md)). A Win32 `SendInput` hot path was evaluated and deferred (no measurable win over `pyautogui` with `PAUSE=0`, plus multi-monitor DPI risk).

## Test layout

Unit tests under `tests/` (pytest). Coverage gate on the whole `autoclicker` package (`cov-fail-under=85`). `tests/test_gui_lifecycle.py` builds the real app with fake Tk widgets and drives every stop path end to end on the real click thread. `scripts/smoke_check.py` verifies imports outside pytest and runs in CI on Python 3.11.
