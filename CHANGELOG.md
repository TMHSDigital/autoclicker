# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Sequence steps beyond clicks (#119): **Add...** in the Sequence panel now adds a click, a hold, a key press, a wait for an image (which can then click it) or a wait for a pixel color. A wait can give up after a timeout and then stop the run or go on to the next step. Every stop path, limit and the failsafe also work while a step waits. Existing sequences and profiles load unchanged. Exported profiles carry each wait step's image inside the file (export format version 2), as image profiles already do.

### Changed

- When a run can't start, the error dialog is titled "Couldn't start" and gives the actual reason (for example "Windows denied access (...)") instead of generic advice such as "Please check your system configuration."
- The step list shows waits of a second or more in seconds and leaves out "wait 0 ms".
- Repository layout: the requirements files moved to `requirements/` (install from source with `pip install -r requirements/runtime-lock.txt`; `run_autoclicker.bat` does this for you), the PyInstaller spec to `packaging/`, and CONTRIBUTING, SECURITY and the Code of Conduct to `.github/`.

### Fixed

- When Start fails with an unexpected error, the error and its traceback now go to `autoclicker.log` as well as the "Couldn't start" dialog, so the problem can be traced (#200).
- Image mode with a wide search area and a tolerance no longer keeps a CPU core busy: after a search that takes longer than 100 ms, the next one waits at least as long, as the performance notes already said (#195).
- `run_autoclicker.bat` checks for Python 3.11 or newer and says so, instead of advertising 3.10 and failing during the install; the antivirus guide names the right versions too (#193).

### Documentation

- The website and README show the current control-panel window, the website hero and social card use one flat blue instead of a gradient, and the home page covers what 1.7.0 added (Spread, Start and Stop at, the portable zip, `--json`). Missing pages get a 404 page with links back, and the developer notes in `docs/` are no longer published as bare web pages. On the home page, the safety stops, install steps and "Who it's for" are plain lists and paragraphs instead of rows of cards.

## [1.7.0] - 2026-11-09

A new dark control-panel window. Click a button wherever it appears on screen, saved in profiles and runnable from the command line, and start or stop at a time of day. Safer edges: no run can start with its stop keys released, a paused run still ends on time, and image clicks never land where the image used to be. Settings lock while clicking, and the screen is searched about three times faster.

### Added

- Image target mode: press Capture and drag a rectangle around a button; each click then goes wherever that image is found nearby (searched within a margin around the capture), and the run waits while it isn't on screen. Matching is exact and needs no extra dependencies (#87).
- Image profiles: a profile saved in Image mode keeps its own captured image, and exporting profiles embeds the picture in the file so it works on another PC. `--image` runs the captured image from the command line, also with `--headless` and `--profile` (#98).
- Image mode: a **Tolerance** setting (0 to 64, 0 = exact as before) finds a button whose colors shift slightly, such as under HDR or Night light; a thumbnail shows the captured image, and **Clear** forgets it (#123).
- **Start at** a time of day (Timing, or `--start-at 09:30`): Start counts down to that time on the wall clock, cancellable like any countdown, claiming the global stop keys only for the last minute. The README explains running on a schedule with Task Scheduler (#121).
- **Spread**: each click can land at a random spot up to N pixels (0 to 50) from its target, like variation does for timing. Works for fixed points, sequence steps and image targets (staying on the image), also as `--spread` and in profiles (#120).
- Portable mode: with a `portable.txt` file next to `WindowsAutoclicker.exe`, settings, logs and captured images stay in a `data` folder beside it instead of `%APPDATA%`. Releases include a ready-made `WindowsAutoclicker-portable.zip`, smoke-tested in CI (#122).

- Sequences: **Edit...** (or double-click or right-click a step) re-picks a step's point, changes its button or single/double click, sets its wait or duplicates it, without removing and re-adding it. Delete, Alt+Up and Alt+Down work on the step list, and **Undo** (Ctrl+Z) brings back the steps from before the last Remove or Record (#175).
- With Windows **High Contrast** on, the window takes the system's colors instead of its own dark palette, custom-drawn controls included (#181).
- The tray menu has a **Profiles** submenu that loads a saved profile into the window, greyed out while a run, countdown or recording is on (#178).
- While a run with limits is going, the Clicks readout shows progress such as `57 / 200`, the Runtime caption counts down to the earliest time limit (auto-stop minutes or Stop at), and the tray tooltip says the same (#173).
- Image mode: **Stop if not seen for** N seconds (or `--image-timeout N`) ends the run once the image has been missing that long in a row, instead of waiting forever; 0, the default, keeps waiting. Saved in profiles (#174).
- **Stop at** a time of day (Timing, or `--stop-at 17:30`), the counterpart to Start at: the run ends the next time the clock shows that time, across midnight too, or earlier if a click or minute limit comes first (#177).
- `--list-profiles` prints the saved profiles with a one-line summary each, and a `--profile` name that doesn't exist now lists the saved ones. `--headless --json` prints the result as one JSON object (`reason`, `message`, `clicks`, `seconds`, `exit_code`) for scripts (#176).
- **Open data folder** in the menu opens the folder with your settings, logs and captured images, in portable mode too (#180).

### Changed

- New dark control-panel window. A large Start/Stop button carries the hotkey and turns amber while counting down and red while running; Clicks, Runtime and Rate readouts and a status line that describes the click settings sit beside it. Target and Click are side-by-side panels with segmented controls; Timing and Safety collapse to a one-line summary of their non-default values; the tray and update toggles live in the footer. The light theme and the sun/moon toggle are gone, and a saved `theme` setting is ignored. Import/Export profiles and Check for updates now moved to the menu in the top-right corner. The success-rate figure no longer shows in the window (it is still in Copy diagnostics).
- The unused `theme` setting is no longer written to new settings files, and `autoclicker.utils.coordinate_picker` (the old name of `autoclicker.utils.profiles`) is scheduled for removal in 2.0 (#172).
- Installing from source or the Python package now asks for the dependency versions CI tests: Pillow 12 or newer (older ones have known image-decoder vulnerabilities), pywin32 306+, pyautogui 0.9.54+, pystray 0.19.5+ and sv-ttk 2.6.1+. The release exe is unaffected (#155).
- Running from source needs Python 3.11 or newer. Python 3.10 reached end of life in October 2026 and Pillow 13 no longer supports it; the release exe already ships with 3.11 and is unaffected.
- First launch shows a short hint with the ways to stop a run, using your own keys (stop key, emergency key, and the screen corners if the failsafe is on) until you press **Got it**. The update-check question moved into that hint as an unticked checkbox instead of a separate dialog (#124).
- The settings are locked while a countdown or run is in progress, since changes would not reach the running clicks; section headers still open. Action choices a target mode can't run are greyed out (Hold and Key in Sequence, Key in Image), switching to such a mode falls back to Click, and X/Y are off when Key is chosen. The status bar's target line follows what you type in X, Y and Key (#102).

### Fixed

- Typing `inf` or `nan` into a number field, or passing it on the command line (`--minutes inf`), no longer crashes the panel summaries or startup; the value counts as unset (#147).
- The numbers above the Start button show in their large type again, and the labels in the header and status line no longer sit on gray boxes: the theme's own colors and fonts were being overridden at startup.
- High Contrast: buttons, fields and the Timing and Safety headers take the system colors too, instead of light gray (the headers were white on gray and hard to read) (#181).
- Hold and Key are shown dimmed where a mode does not allow them (as in Sequence mode), instead of looking like raised buttons.
- The sequence step list is wider and its lines shorter ("wait 500 ms"), so a step's button, click type and wait are no longer cut off.
- If a hotkey could not be registered at startup (say F6 is taken by another program), every hotkey stopped working for the session, Stop and Emergency stop included, and the "Hotkey unavailable" message was lost. Now only the taken key is missing and the message shows once the window is up (#144).
- A settings file that is not UTF-8 (say, saved as ANSI from Notepad) is now moved aside as a `.corrupt-` copy with a warning, like invalid JSON, instead of being replaced by defaults at the next save or stopping the app from starting. A settings file that can't be opened (locked by another program) loads defaults with a warning and is not saved over during that session. A hand-edited `max_cps_ceiling` that isn't a number no longer stops the app from starting (#146).
- A settings change that can't be written (full disk, read-only folder, antivirus lock) now shows "Settings not saved" in the status line instead of only in the log, and the Hotkeys dialog says the new keys apply to this session only (#151).
- The Runtime and Rate readouts keep the last run's figures instead of counting on after it ended (they changed when a countdown was cancelled or Stop was pressed while idle), and the Timing summary no longer lists the start delay when **Start at** is set, since Start counts down to that time instead (#148).
- A speed limit below 8 clicks per second now stops the run at the first press over the limit; before, the guard waited for 8 presses in a second whatever the limit (#149).
- `--headless` claims the Stop and Emergency keys before the first click instead of just after clicking started (#150).
- Captured and imported images are only ever read as PNG, the format the app writes, so other image decoders never run on a shared profile (#157).
- Image mode: Start no longer freezes the window for a second or two with a large capture (preparing a full-screen image went from about 1 to 2 s to about 0.1 s, and later Starts reuse it), searches with a **Tolerance** are about a third faster, and a slow wide-margin search no longer keeps a processor core busy for the whole run (#161, #162).
- Image mode only opens images from its own images folder, where captures and imported profile images are kept; a settings or profile entry that points anywhere else asks you to capture the image again.
- The window appears sooner: PyAutoGUI and the update checker's web client are no longer imported at startup (PyAutoGUI loads in the background once the window is up), which saves 0.3 to 1 s per launch when running from source and a little in the exe (#163).
- The exe no longer bundles mouseinfo and pymsgbox (GPLv3+, optional pyautogui imports the app never used) or pyperclip. Releases now ship `THIRD_PARTY_NOTICES.txt` with the license of every bundled package, inside the exe, in the portable zip and as a release download (#153).
- Stopping a run (button, hotkey, tray, Quit) no longer freezes the window for about a second, and Stop while recording no longer blocks it for up to two seconds. Background threads now hand their updates to the window through a queue instead of calling it directly (#145).
- Hint, summary and error text now meet WCAG AA contrast (the gray was 2.9:1, the error red 3.2:1) (#104).
- The Hotkeys dialog can no longer be opened during the Start countdown, while recording or while picking, and nothing starts while it is open. Before, a countdown could finish behind the dialog and start a run with every global stop key released (#93).
- Emergency stop while the picker is open now stops a running engine too, instead of only closing the picker. Start (button, hotkey, tray) is refused while picking or recording, so a countdown can no longer end on the picker overlay or release the recorder's stop keys (#95).
- A run paused by **Pause when unfocused** now stops when its auto-stop time is up, instead of staying paused until the window came back. A `--headless` run started from a terminal no longer takes the terminal as its target window, which left it paused for good (and, with the first fix missing, never exiting) (#94).
- Image target mode no longer clicks the old position again after a click makes the image disappear: each click needs a search that started after the previous click (#96).
- Copy diagnostics no longer includes the captured image's path or search area, and replaces your Windows user folder (which contains the account name) everywhere in the report, including the log lines (#99).
- Quitting with one invalid field no longer throws away every other unsaved change: the invalid field keeps its last saved value and the rest is saved (#101).
- Image mode: changing the search margin now takes effect at the next Start instead of needing a recapture (`image_region` now stores where the image was captured; older saved areas just search a little wider). Replacing a capture deletes the old file unless a profile uses it. A screen that can't be read ends the run with an error after about two seconds instead of waiting silently, an oversized or malformed image file reports an error instead of crashing Start, and the capture overlay keeps its own hint, shows the rectangle's size while dragging and explains a too-small drag (#100).
- The one-time migration of settings from older versions now only looks next to the app (the exe's folder, or the source checkout), never in whatever folder the app was started from, and a failed migration no longer makes the app save to the old file, which lost the session's changes (#105).
- Smaller fixes (#103): Record's replace prompt has a Cancel that discards the recording, and a recording longer than a sequence holds says how many steps were kept. The mouse wheel no longer scrolls the settings behind a dialog, the step list or a text box, and precision touchpads scroll. Emergency stop with nothing running no longer shows a red error. The first-run update question waits until no run or countdown is in progress, an update check that fails (say, offline) is retried at the next launch instead of a day later, and the Update button only opens this project's release pages.
- Image mode grabs only the searched area of the screen instead of the whole desktop and prepares the captured image once per run, cutting each search from about 50 ms to about 17 ms on a two-monitor desktop and keeping the click thread's timing steady (#97).
- Building the Python package from a source checkout no longer sweeps a local `autoclicker_env` virtualenv into the wheel and sdist (the package pattern `autoclicker*` matched it); CI now builds and checks the package on every run, ready for PyPI (#118).
- Real-input integration tests no longer fail intermittently on the CI runner while starting Tk.

### Security

- Release builds install from lock files with hashes (`--require-hashes`), only the tag-only signing job can request an OIDC token, `build` and `twine` come from the locked dev tools, and the portable zip gets a build provenance attestation like the exe, so `gh attestation verify` works on both (#156).
- Pillow 13.0.0 closes nine advisories in its image decoders (GHSA-8g5g-8vmr-9782, GHSA-pchr-8j38-3x4p, GHSA-c6hw-5grf-ff96, GHSA-58r4-6rv3-gfh8, GHSA-65qm-jvmh-6pqg, GHSA-q45j-58j2-45rg, GHSA-p4wg-p73j-c528, GHSA-462x-pgg6-55fp and GHSA-vx6w-vv9f-6gvg). certifi 2026.10.19 drops the emSign root CAs (GHSA-6q48-6c7w-9gw2) used by the dev tools.

### Documentation

- The README, website and guides use the new panel and field names (Click panel, Every, Search, the status line, Pause when the target window isn't in front), show the dark screenshot only, and list `--version`. The bug report form offers Sequence and Image as target modes (#159, #160).

- Troubleshooting covers antivirus false positives (how to verify the download and report it) and an image that is never found; the website FAQ answers the antivirus question too (#114).
- The website shows recording and image targets, the Scoop install command and the current version and size, with a search-friendly title, structured data (app and FAQ), complete social preview tags, robots.txt and a sitemap (#116).
- README and website say who the app is for (easing repetitive strain, testing, repetitive work, games where allowed), and release notes now open with how to install and a short summary (#117).
- Six step-by-step guides on the website (record a routine, click an image, run on a schedule, easing clicking strain, verifying a download, SmartScreen and antivirus warnings), linked from the home page and listed in the sitemap (#125).

## [1.6.0] - 2026-10-05

### Added

- Record a sequence: press Record in the sequence panel and click through the routine once; each click becomes a step with its button and the measured wait, and quick repeat clicks become double clicks. The Stop key or Record again finishes. Only clicks are recorded, and the mouse hook exists only while recording (#86).
- Info dialog with **Copy diagnostics**: one click copies the app version, Windows and display details, settings (profile names, sequence points and the watched pixel left out) and the log tail for a bug report, after showing exactly what will be copied. Also in the tray menu as About and diagnostics (#88).
- The repository shows a Sponsor button, and the Info dialog mentions sponsorship once, with no reminders (#90).
- Install with Scoop: `scoop bucket add tmhs https://github.com/TMHSDigital/autoclicker`, then `scoop install tmhs/windows-autoclicker`. winget manifests are generated with each release (#76).
- Project website at https://tmhsdigital.github.io/autoclicker/ and GitHub Discussions for questions, linked from the new-issue page (#77).

### Changed

- Advanced is split into three collapsed sections, **Timing**, **Safety** and **App**, and Start, Stop, the status panel and the footer stay pinned at the bottom of the window, so they remain visible on small screens however many sections are open (#85).

### Fixed

- The corner failsafe now works during a Hold; previously a hold of up to 60 seconds ignored the corner until it ended. The button is released and the run stops within about 50 ms (#82).
- Pause when unfocused: a sequence whose steps click into different windows no longer pauses for good after the first switch; any step's window counts as in front. A run started from the Start button no longer waits for you to activate the target window yourself: the first click brings it forward (#81).

### Documentation

- CONTRIBUTING.md records the license decision (CC BY-NC 4.0 kept) and that contributions are licensed under the same terms (#71).

## [1.5.0] - 2026-10-04

### Added

- Only click while a pixel matches (Advanced, Only when): sample a point's color with the picker, then clicking either waits (shown as Paused) or stops whenever that pixel no longer matches within a tolerance. Checked before every burst and sequence step; the screen is read on a separate thread so clicking isn't slowed down (#80).
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

- README: a short "Why this one" section, refreshed light and dark screenshots of the new window, and a 1280x640 social preview image (`docs/images/social-preview.png`, drawn by `tools/make_social_preview.py`) (#77).
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

[Unreleased]: https://github.com/TMHSDigital/autoclicker/compare/v1.7.0...HEAD
[1.7.0]: https://github.com/TMHSDigital/autoclicker/releases/tag/v1.7.0
[1.6.0]: https://github.com/TMHSDigital/autoclicker/releases/tag/v1.6.0
[1.5.0]: https://github.com/TMHSDigital/autoclicker/releases/tag/v1.5.0
[1.4.1]: https://github.com/TMHSDigital/autoclicker/releases/tag/v1.4.1
[1.4.0]: https://github.com/TMHSDigital/autoclicker/releases/tag/v1.4.0
[1.3.0]: https://github.com/TMHSDigital/autoclicker/releases/tag/v1.3.0
[1.2.0]: https://github.com/TMHSDigital/autoclicker/releases/tag/v1.2.0
[1.1.0]: https://github.com/TMHSDigital/autoclicker/releases/tag/v1.1.0
