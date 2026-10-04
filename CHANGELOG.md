# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Action setting (Click Settings): **Hold** presses the mouse button for a set time and releases it, and **Key** presses a key or combo such as F5 or Ctrl+R in the focused window, both on the same interval, burst, limits and stop paths. A held button is released on every stop, including emergency stop and the failsafe; a key can't be one of the app's own hotkeys. Also `--hold MS` and `--key KEY` on the command line (#78).
- Opt-in update check: asked once on first launch (and changeable under Advanced), the app checks GitHub at most once a day and shows an "Update to X" button plus a tray notification when a newer release exists. It never checks while clicking, never downloads anything, and makes no network requests when off (#79).
- Command line: flags such as `--profile`, `--at X,Y`, `--cursor`, `--interval 100ms`, `--clicks N`, `--start` and `--minimized` set up the window for one launch, and `--headless` runs once without a window (hotkeys, failsafe and limits still apply) and exits with a code that says how the run ended. Saved settings are left alone (#75).
- Sequence target mode: click several points in order, each with its own button, click type and wait before the next step, repeated N times or until stopped. Points are added with Pick Location and can be reordered or removed; every stop path and limit is checked before each step, and sequences are saved in settings and profiles (#72).
- Presets are now profiles: besides the target point they remember the target mode, interval, variation, button, click type, burst and limits, and loading one restores them all. Saving over an existing name asks first, a summary line shows what the selected profile does, and profiles can be exported to and imported from a JSON file. Presets saved by older versions still load (#73).
- Start countdown: the Start button and the tray menu wait 3 seconds before clicking (Advanced, Start delay; 0 to 60, 0 starts at once), showing "Starting in N...". Stop, Emergency stop and the toggle key cancel it; the Start hotkey still starts immediately (#74).
- Speed limit setting under Advanced for the runaway guard (previously only editable in the settings file). Setting it to 0 asks for confirmation (#64).
- Minimize to tray (Advanced, on by default): minimizing hides the window to the tray icon, with a one-time reminder that clicking continues. Double-clicking the tray icon restores the window, and its tooltip shows the current state and click count (#49).
- Configurable hotkeys under Advanced, Hotkeys: rebind Start, Stop and Emergency stop, or add a single start/stop toggle key. Buttons and the tray menu show the current keys (#47).
- "Current cursor position" target mode: hover over something and press F6 to click wherever the cursor is, with no coordinates to pick (#48).

### Changed

- The app now declares per-monitor DPI awareness itself, before PyAutoGUI loads, so picked and clicked coordinates use physical pixels on every monitor, including monitors with different scaling (#67).
- Releases ship a SHA-256 checksum and a GitHub build provenance attestation, release notes contain only that version's changes, and the exe has Windows version details and is no longer UPX-compressed (fewer antivirus false positives). See docs/RELEASING.md (#45).
- New app icon matching the README logo. Icons now ship inside the package (`autoclicker/assets/`), so `pip`/`pipx` installs show the real window and tray icon instead of a red square. Package metadata uses the SPDX license field (#58).
- Hotkeys are now exclusive while claimed: a pressed hotkey goes only to the autoclicker. To keep Esc usable in other programs, the Stop and Emergency keys are claimed only while clicking and the Start key only while idle. A key that another program already owns is reported in the status bar.

### Fixed

- The status bar's Target line shows the saved point (or cursor/sequence mode) at launch and follows changes, instead of always reading "(100, 100)" until the first run.
- The status bar's success rate is per run; it used to add up every run since launch, and a failed click was counted twice (#68).
- The app icon in the title row shows again; it was looked up in the current directory instead of the package (#68).
- The corner failsafe works on every monitor, not just the primary one. Corners where two screens meet are ignored, so moving between monitors never stops a run (#66).
- An unreadable settings file (for example after a hand edit with a typo) is moved aside as `autoclicker_settings.json.corrupt-<time>` and the status bar says so, instead of being overwritten by defaults on the next save and losing presets and hotkeys. Individual values of the wrong type fall back to their defaults without affecting the rest (#65).
- The runaway guard counts both presses of a double click, so Double can no longer run at twice the limit, and ceilings above 1,023 clicks per second can now actually trip (#64).
- Pause when unfocused no longer stalls after one click when a run is started with the Start button or the tray menu. It used to remember the autoclicker's own window as the one that must stay in front; it now uses the window under the target (or, in cursor mode, the next window you bring to the front). While paused, the status bar and tray tooltip say so instead of "Running..." (#63).
- In Fixed location mode every click now goes to the target. Previously, once the first click had moved the cursor there, moving the mouse during a run made the following clicks land wherever the cursor was (#62).
- The window opens at the size of its content, so the footer is no longer cut off with a scrollbar on first launch.
- Saved presets and hotkeys could leak into the built-in defaults, so resetting settings brought deleted presets back. Defaults are now copied, never shared.
- `sessions.log` is rotated at 1 MB (3 backups) instead of growing forever, and writes from the UI and click threads no longer interleave. If `APPDATA` is not set, settings and logs go to the roaming profile folder instead of the current directory (#54).
- Only one copy runs at a time. Launching it again brings the running window to the front (even from the tray) instead of starting a second clicker with its own hotkeys, which used to double the click rate (#50).
- Pick Location no longer sends the pick click to the window underneath. It now shows a dimmed overlay across all monitors with a crosshair and a live X, Y readout; Esc or right-click cancels (#43).
- Double click now works with the right and middle buttons; it used to send a single click (#51).
- Status bar: the click counter and runtime show exact totals when a run ends instead of the last one-second update, safety stops and errors are shown in red, and the runtime placeholder matches the live format (#53).
- Stop and Emergency Stop no longer also report the run as "completed": the status keeps showing "Emergency stop" and `sessions.log` gets exactly one stop line per run with the real reason (#41).
- Errors during a run (for example coordinates that went off screen after a display change) are shown in the status bar and a dialog instead of a plain "Stopped", and are logged with a traceback (#42).
- Pressing Start while the previous run is still shutting down now says so instead of doing nothing.
- Click and time limits report what happened, e.g. "Done: reached 1,000 clicks".
- Auto-stop, the runaway guard and the runtime display use a monotonic clock, so a system clock change during a session no longer stops it early, keeps it running past its limit, or shows a negative runtime (#52).
- Multiple monitors are supported. Coordinates are checked against the whole desktop instead of the primary screen, so picks on a monitor to the right are no longer rejected and picks on a monitor to the left (negative X) click where they should (#40). The rightmost and bottom edge pixels are no longer accepted as on-screen.
- Invalid input is now reported instead of silently rewritten. Previously an interval of `-500` ran at maximum speed, `1OO` ran at 1000 ms, and a negative X clicked at the left edge of the screen (#39). Validation errors name the field in plain words.

### Removed

- The `keyboard` and `mouse` dependencies (unmaintained since 2020). Hotkeys now use Win32 `RegisterHotKey`, so the app no longer installs a system-wide keyboard or mouse hook (#57).
- The "Enable click queuing" option. With it on, Stop could keep clicking for seconds and later runs never clicked (#38). The direct click path is now the only one.

### Documentation

- Security reports go through GitHub private vulnerability reporting (email still works), and CodeQL now scans the Python code and the workflows on every push and weekly (#70).
- Bug and feature reports use GitHub issue forms that ask for the app version, how the app is run, monitor scaling and the log tail; blank issues are off and security reports are routed to private reporting (#69).
- The burst row reads "Burst: N clicks, N ms apart" instead of an ambiguous "Pause", and CONTRIBUTING.md matches the real workflow: commit conventions, lock files, checks and release steps (#46).
- README redesigned: download-first hero, timing diagram for interval vs. burst pause, accurate safety, settings and troubleshooting sections, and known limitations.

## [1.4.1] - 2026-10-04

### Security

- Bundled Pillow updated to 12.3.0, which fixes several published advisories in 12.2.0.

### Changed

- Bundled pywin32 updated to 312.
- CI actions updated (checkout v7, setup-python v7, codecov v7, action-gh-release 3.0.3); Dependabot now tracks `sv-ttk`.

## [1.4.0] - 2026-08-28

### Fixed

- Click loop now clears `is_running` on auto-stop, failsafe, and errors so Start works again.
- Emergency stop drops the click queue instead of leaving queued clicks firing.
- Safety stop no longer joins the click thread from inside it.
- Settings saves are atomic; invalid quit settings no longer overwrite the last-good file.
- Pause-when-unfocused fails closed if the foreground window cannot be read.
- Hotkeys, tray, picker, and engine callbacks update Tk on the main thread.
- ESC during Pick Location cancels picking instead of emergency-stopping.
- Coordinate picker no longer hides the window if picking fails to start.

### Added

- Delete-preset control, failsafe-off confirmation, AppData rotating log, packaged icon path resolution.

### Changed

- Python 3.10+ is the documented floor; launcher and contributor venv are `.venv`.
- Coverage gate is package-wide (65%). CI smoke-checks imports. Public docs drop “anti-detection” wording.

## [1.3.0] - 2026-05-30

### Changed

- UI/UX refresh: modern Sun Valley (`sv-ttk`) theme with light/dark toggle (persisted via new `theme` setting) and Segoe UI typography.
- Simplified default view: burst mode, safety limits, and advanced toggles moved into a collapsible "Advanced" section (collapsed by default).
- Status panel reworked into a compact status bar with a colored state indicator and inline metrics.
- Disclaimer reduced to a one-line footer with an info dialog; removed the always-on horizontal scrollbar, and the vertical scrollbar now auto-hides when content fits.
- Documentation: added UI screenshots to the README, moved `ARCHITECTURE.md` and `PERFORMANCE.md` under `docs/`, and removed one-time audit/hardening artifacts.

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

[Unreleased]: https://github.com/TMHSDigital/autoclicker/compare/v1.4.1...HEAD
[1.4.1]: https://github.com/TMHSDigital/autoclicker/releases/tag/v1.4.1
[1.4.0]: https://github.com/TMHSDigital/autoclicker/releases/tag/v1.4.0
[1.3.0]: https://github.com/TMHSDigital/autoclicker/releases/tag/v1.3.0
[1.2.0]: https://github.com/TMHSDigital/autoclicker/releases/tag/v1.2.0
[1.1.0]: https://github.com/TMHSDigital/autoclicker/releases/tag/v1.1.0
