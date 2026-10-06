<div align="center">

<img src="docs/images/logo.svg" alt="Windows Autoclicker logo" width="112" />

# Windows Autoclicker

**A fast, careful autoclicker for Windows: pick a spot, set the pace, press F6.**

Pixel-precise clicking with burst mode, timing variation, named profiles and global hotkeys,<br />
built around safety stops that are on by default.

<br />

[![Download for Windows](https://img.shields.io/github/v/release/TMHSDigital/autoclicker?style=for-the-badge&logo=windows&logoColor=white&label=Download%20for%20Windows&color=0078D4&labelColor=005A9E)](https://github.com/TMHSDigital/autoclicker/releases/latest/download/WindowsAutoclicker.exe)

<sub>Single <code>.exe</code> · no install, no Python · Windows 10 and 11 · <a href="https://github.com/TMHSDigital/autoclicker/releases">all releases</a></sub>

<br />
<br />

[![CI](https://img.shields.io/github/actions/workflow/status/TMHSDigital/autoclicker/ci.yml?branch=main&style=flat-square&label=CI)](https://github.com/TMHSDigital/autoclicker/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/TMHSDigital/autoclicker?style=flat-square&color=0078D4)](https://github.com/TMHSDigital/autoclicker/releases)
[![Python](https://img.shields.io/badge/python-3.10--3.14-3776AB?style=flat-square&logo=python&logoColor=white)](#run-from-source)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-0078D4?style=flat-square)](#quick-start)
[![License: CC BY-NC 4.0](https://img.shields.io/badge/license-CC%20BY--NC%204.0-lightgrey?style=flat-square)](LICENSE)
[![Sponsor](https://img.shields.io/badge/sponsor-%E2%99%A5-ea4aaa?style=flat-square&logo=githubsponsors&logoColor=white)](https://github.com/sponsors/TMHSDigital)

<br />

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/screenshot-dark.png" />
  <source media="(prefers-color-scheme: light)" srcset="docs/images/screenshot-light.png" />
  <img src="docs/images/screenshot-light.png" alt="Windows Autoclicker main window: target coordinates, click settings, start and stop controls, and a status bar" width="440" />
</picture>

<br />
<br />

[Why this one](#why-this-one) ·
[Quick start](#quick-start) ·
[Features](#features) ·
[How timing works](#how-timing-works) ·
[Sequences](#sequences) ·
[Image targets](#image-targets) ·
[Command line](#command-line) ·
[Hotkeys](#hotkeys) ·
[Safety](#safety) ·
[Settings](#settings-and-logs) ·
[Troubleshooting](#troubleshooting) ·
[Contributing](#contributing)

</div>

<br />

## Features

<table>
  <tr>
    <td width="33%" valign="top">
      <h3>Pick and click</h3>
      Click a fixed spot (type X/Y, or <b>Pick Location</b> with a live coordinate readout on any monitor), or wherever the <b>cursor</b> is, or a <b>sequence</b> of points clicked in order, or wherever a captured <b>image</b> appears. Save the spot and its click settings as named <b>profiles</b>, and import or export them as a file.
    </td>
    <td width="33%" valign="top">
      <h3>Precise timing</h3>
      Intervals in milliseconds or seconds, down to <b>0&nbsp;ms</b>, with optional <b>± variation</b> so the cadence isn't perfectly regular.
    </td>
    <td width="33%" valign="top">
      <h3>Burst mode</h3>
      Fire several clicks in quick succession, then wait the interval. Left, right or middle button; single or double click. Or <b>hold</b> the button for a set time, or press a <b>key</b> such as <kbd>F5</kbd> instead of clicking.
    </td>
  </tr>
  <tr>
    <td width="33%" valign="top">
      <h3>Safety on by default</h3>
      Corner failsafe, emergency stop, click and time limits, a runaway-speed guard, and an optional pause when your target window loses focus.
    </td>
    <td width="33%" valign="top">
      <h3>Global hotkeys</h3>
      <kbd>F6</kbd> start, <kbd>F7</kbd> stop, <kbd>Esc</kbd> emergency stop, all rebindable, plus an optional start/stop toggle key. They work while the app is in the background.
    </td>
    <td width="33%" valign="top">
      <h3>Remembers you</h3>
      Light and dark themes, and every setting is saved to your profile and restored on next launch.
    </td>
  </tr>
</table>

## Why this one

- **Stops when you need it to.** Corner failsafe on every monitor, an emergency key, click and time limits, a runaway-speed guard, pause when your target window loses focus, and an optional "only while this pixel matches" check. All on by default where it makes sense, and a held button is always released.
- **Builds you can check.** Every release is built by GitHub Actions from this repository and ships with a SHA-256 checksum and a build provenance attestation. The source is right here to read.
- **Quiet on your system.** One `.exe`: no installer, no ads, no bundled offers. Hotkeys use Windows `RegisterHotKey` instead of a system-wide keyboard hook, and the app makes no network requests unless you turn on the daily update check.
- **More than one spot.** Record a routine by clicking through it once, click a button wherever it appears on screen, hold and key actions, profiles you can export and share, and a command line with a headless mode for scripts and shortcuts.

## Who it's for

- **Easing repetitive strain.** If clicking hurts (RSI, tendon problems, limited hand mobility), let the app do the repeated clicks: long holds, key repeat and a start/stop key mean you press once instead of hundreds of times. It does not replace accessibility software or medical advice.
- **Testing and QA.** Repeat a click path to reproduce a bug, soak-test a button, or keep a test app busy; the command line exits with a code that says how the run ended.
- **Repetitive data entry and admin work.** Click through the same dialog or form step after step, with waits that match how fast the app responds.
- **Idle and incremental games**, where the game's rules allow it. Many online games forbid automation; check before you use it.

## Quick start

<table align="center">
  <tr>
    <td align="center" width="25%"><h3>1</h3><b>Download</b><br /><sub><a href="https://github.com/TMHSDigital/autoclicker/releases/latest/download/WindowsAutoclicker.exe"><code>WindowsAutoclicker.exe</code></a></sub></td>
    <td align="center" width="25%"><h3>2</h3><b>Run it</b><br /><sub>no installer, no Python</sub></td>
    <td align="center" width="25%"><h3>3</h3><b>Pick a target</b><br /><sub><b>Pick Location</b>, or use the cursor</sub></td>
    <td align="center" width="25%"><h3>4</h3><b>Press <kbd>F6</kbd></b><br /><sub><kbd>F7</kbd> or <kbd>Esc</kbd> to stop</sub></td>
  </tr>
</table>

> [!NOTE]
> The executable isn't code-signed, so Windows SmartScreen may say *"Windows protected your PC"*. Choose **More info → Run anyway**. Every release is built from this repository by [CI](https://github.com/TMHSDigital/autoclicker/actions/workflows/ci.yml) and ships with a SHA-256 checksum and a build provenance attestation; see [how to verify a download](docs/RELEASING.md#verifying-a-download).

With [Scoop](https://scoop.sh/):

```powershell
scoop bucket add tmhs https://github.com/TMHSDigital/autoclicker
scoop install tmhs/windows-autoclicker
```

<details>
<summary><b id="run-from-source">Run from source</b> (Python 3.10 to 3.14)</summary>

<br />

```bash
git clone https://github.com/TMHSDigital/autoclicker.git
cd autoclicker
run_autoclicker.bat
```

`run_autoclicker.bat` creates a `.venv`, installs the pinned dependencies from `requirements-lock.txt` and starts the app. To do it by hand:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-lock.txt
python autoclicker.py
```

Or install it as a command with [pipx](https://pipx.pypa.io/):

```bash
pipx install git+https://github.com/TMHSDigital/autoclicker.git
autoclicker
```

</details>

## How timing works

Three settings control the rhythm. With **Burst clicks** left at 1 (the default), only the interval matters: one click, wait, repeat.

<p align="center">
  <img src="docs/images/timing.svg" alt="Timing diagram: three clicks separated by the burst pause form a burst; the interval plus or minus variation separates one burst from the next" width="760" />
</p>

<div align="center">

| Setting | What it controls | Range |
| :-- | :-- | :-: |
| **Interval**<br /><sub>Click Settings</sub> | Wait between bursts (or between clicks, when a burst is 1 click) | 0 to 60 000 ms<br /><sub>or 0.001 to 60 s</sub> |
| **± variation**<br /><sub>Click Settings</sub> | Random offset added to each interval | 0 ms to just under<br /><sub>the interval</sub> |
| **Burst clicks**<br /><sub>Timing, Burst</sub> | Clicks fired per burst | 1 to 100 |
| **Burst pause**<br /><sub>Timing, "ms apart"</sub> | Wait between the clicks *inside* a burst | 0 to 60 000 ms |

</div>

## Sequences

Choose **Sequence** under Target to click several points in order, for example *claim, close, next*.

1. Press **Record** and click through the routine once, then press **Record** again (or the Stop key). Each click becomes a step with the button you used, and the time between clicks becomes the wait; two quick clicks on the same spot become a double click. Or press **Add point** and pick each spot by hand; those steps use the button and click type selected in Click Settings.
2. Select a step and use **Wait...** to set how long to wait before the next step (500 ms by default), or **Up**, **Down** and **Remove** to rearrange.
3. Set **Repeat** to run the whole sequence that many times (0 keeps going until you stop it). The main **Interval** is the wait between rounds; burst settings don't apply.

Every stop path works mid-sequence: hotkeys, the corner failsafe, click and time limits, the runaway guard and pause when unfocused are all checked before each step. Up to 50 steps; a sequence is saved with your settings and inside profiles. Recording only notes where you click and when, never keystrokes, and uses a mouse hook that exists only while recording.

## Image targets

Choose **Image** under Target to click a button wherever it shows up, even after its window moves.

1. Press **Capture...** and drag a rectangle around the button. The app saves that image and searches for it within **Search** px around the spot (150 by default).
2. Start as usual. Each click goes to the center of the image where it was last found; while it isn't on screen the run waits and the status bar says so.

Matching is exact, so recapture if the button changes look (hover states, a different theme or scaling). Searching a small area keeps it fast without extra dependencies. Each click waits for a fresh search that started after the previous click, so a click that closes the image is never repeated on whatever is underneath; image mode therefore clicks at most about 10 times a second. Every stop path, limit and the runaway guard work as usual.

## Command line

Flags override your saved settings for one launch: they fill in the window, and `--start` presses Start for you (with the usual countdown). Handy for desktop shortcuts, Task Scheduler or a macro pad.

```bat
WindowsAutoclicker.exe --profile Work --start --minimized
WindowsAutoclicker.exe --at 800,600 --interval 250ms --button right --clicks 100 --start
autoclicker --cursor --interval 50ms --clicks 200 --headless
```

| Flag | Meaning |
| :-- | :-- |
| `--at X,Y`, `--cursor`, `--sequence`, `--image` | Target: a point, wherever the cursor is, the saved sequence, or wherever the captured image appears (the saved capture, or the one in `--profile`) |
| `--profile NAME` | Load a saved profile first (other flags apply on top) |
| `--interval 100ms` / `2s`, `--variation MS` | Timing |
| `--button left\|right\|middle`, `--double`, `--single` | What to click |
| `--hold MS`, `--key KEY` | Hold the button, or press a key, instead of clicking |
| `--burst N:MS`, `--clicks N`, `--minutes N`, `--repeat N` | Bursts, limits and sequence rounds |
| `--delay SECONDS` | Countdown before clicking starts |
| `--start`, `--minimized` | Press Start after launch; start hidden in the tray |
| `--headless` | No window: run once, then exit. Hotkeys, the corner failsafe and every limit still apply, and saved settings are left alone |

A headless run exits with `0` when it finishes or you press Stop, `2` for bad options, `3` after an emergency stop, `4` for the failsafe or runaway guard, `5` on an error and `6` if the app is already running. `--help` lists everything; the `.exe` shows it in a dialog.

## Hotkeys

<table align="center">
  <thead>
    <tr><th align="center">Key</th><th align="left">Action</th><th align="left">Notes</th></tr>
  </thead>
  <tbody>
    <tr><td align="center"><kbd>F6</kbd></td><td>Start clicking</td><td>Same as the <b>Start</b> button</td></tr>
    <tr><td align="center"><kbd>F7</kbd></td><td>Stop clicking</td><td>Same as the <b>Stop</b> button</td></tr>
    <tr><td align="center"><kbd>Esc</kbd></td><td>Emergency stop</td><td>Halts immediately; cancels <b>Pick Location</b> if picking</td></tr>
  </tbody>
</table>

<p align="center"><sub>Hotkeys are global: they work while another window has focus. Change them, or add a single start/stop <b>toggle</b> key, under <b>App → Hotkeys…</b><br />The Stop and Emergency keys are only claimed while clicking, so <kbd>Esc</kbd> keeps working in other programs the rest of the time.</sub></p>

## Safety

An autoclicker that won't stop is worse than none, so every run has more than one way out.

<table>
  <tr>
    <td width="50%" valign="top">
      <b>Stop it yourself</b>
      <ul>
        <li><b>Corner failsafe</b> (on by default): slam the mouse into a corner of any monitor to abort; checked before every click. Corners where two screens meet don't count, so moving between monitors is safe. Turning it off asks for confirmation.</li>
        <li><b>Emergency stop</b>: <kbd>Esc</kbd> or the red button, from anywhere.</li>
        <li><b>Start countdown</b>: the Start button and tray menu wait 3 seconds before clicking (Timing, Start delay; 0 starts at once), so you can let go of the mouse. Any stop key cancels it. The Start hotkey always starts immediately. While counting down or clicking, the settings are locked (they would not change the running clicks); section headers still open so you can look.</li>
        <li><b>Tray icon</b>: Show, Start, Stop and Exit from the notification area. Minimizing hides the window there (App, on by default); double-click the icon to bring it back.</li>
      </ul>
    </td>
    <td width="50%" valign="top">
      <b>Let it stop itself</b>
      <ul>
        <li><b>Limit clicks</b>: stop after N clicks (Safety, Limits).</li>
        <li><b>Auto-stop</b>: stop after N minutes (Safety, Limits).</li>
        <li><b>Runaway guard</b>: stops if more than 50 button presses land in any one second (a double click is two). Change it under <b>Safety, Speed limit</b>; 0 turns it off after a confirmation.</li>
        <li><b>Only when a pixel matches</b> (Safety, Only when): <b>Sample...</b> a point's color, then clicking waits (or stops) whenever that pixel changes, so a run doesn't keep clicking after the window it was meant for closes or moves.</li>
        <li><b>Pause when unfocused</b>: pauses whenever the target window isn't in front, and the status bar shows <b>Paused</b>. The target window is the one in front when you press the Start hotkey, or the window under the target point when you press the Start button; the first click brings it to the front. In a sequence, any window a step clicks into counts. In cursor mode it's the next window you bring to the front. A <code>--headless</code> run typed into a terminal treats that terminal like the autoclicker's own window, so it is never taken as the target. Paused time counts toward auto-stop, which still ends a paused run on time. Refuses to start if it can't read the foreground window.</li>
      </ul>
    </td>
  </tr>
</table>

> [!IMPORTANT]
> Use it only on software and systems you're allowed to automate, and within their terms of service. Many online games and services forbid automated input. Responsibility for how it's used rests with the user.

### Known limitations

- Windows blocks input from normal apps into **elevated (admin) windows**. To click into one, run the autoclicker as administrator too; otherwise there's no need to.

## Settings and logs

Everything lives in **`%APPDATA%\WindowsAutoclicker\`**. Paste that into Explorer's address bar to open it.

<div align="center">

| File | Contents |
| :-- | :-- |
| `autoclicker_settings.json` | Your settings and profiles, saved when you start clicking, change the theme or profiles, and on exit (a field that is invalid then keeps its last saved value) |
| `autoclicker.log` | Application log, rotated at 1 MB (keeps 2 backups) |
| `sessions.log` | One line per run start and stop, with the stop reason and click count; rotated at 1 MB (keeps 3 backups) |

</div>

<details>
<summary><b>All settings keys</b></summary>

<br />

| Key | Default | Meaning |
| :-- | :-: | :-- |
| `target_mode` | `"fixed"` | `"fixed"` clicks at X/Y; `"cursor"` clicks wherever the cursor is; `"sequence"` clicks the steps in `sequence`; `"image"` clicks wherever the captured image appears |
| `image_path`, `image_region` | `""`, `[]` | Image mode: the captured PNG (saved under `%APPDATA%\WindowsAutoclicker\images\`) and the `[left, top, width, height]` rectangle where it was captured. Replacing a capture deletes the old file unless a profile uses it |
| `image_margin` | `150` | Pixels around the capture to search, 0 to 2 000; applied when a run starts, so changing it needs no recapture |
| `sequence` | `[]` | Steps for sequence mode: `[{"x": 800, "y": 600, "button": "left", "click_type": "single", "delay_ms": 500}, ...]`; `delay_ms` is the wait before the next step |
| `sequence_repeat` | `0` | Rounds to run in sequence mode; `0` = until stopped |
| `x_coord`, `y_coord` | `100` | Target position in desktop pixels; negative on monitors left of or above the primary |
| `interval` | `1000` | Wait between bursts, in `interval_unit` |
| `interval_unit` | `"ms"` | `"ms"` or `"seconds"` |
| `variation` | `0` | ± random milliseconds added to each interval |
| `mouse_button` | `"left"` | `"left"`, `"right"` or `"middle"` |
| `click_type` | `"single"` | `"single"` or `"double"`, for any button. A double click counts as one click toward limits and two presses toward the runaway guard |
| `action` | `"click"` | `"click"`; `"hold"` presses the button for `hold_ms`, then releases it (always released when a run stops); `"key"` presses `key` in whatever window has focus. Sequences always click |
| `hold_ms` | `500` | Hold time in milliseconds, 1 to 60 000 |
| `key` | `""` | Key or combo for the Key action, e.g. `"f5"`, `"space"`, `"ctrl+r"`; can't be one of the app's own hotkeys |
| `condition` | `"none"` | `"wait"` pauses and `"stop"` ends the run while the pixel at `condition_x`, `condition_y` isn't `condition_color` (within `condition_tolerance` per channel); `"none"` turns it off |
| `condition_x`, `condition_y`, `condition_color`, `condition_tolerance` | `0`, `0`, `"#000000"`, `16` | The watched pixel, its expected color, and how far each RGB channel may differ (0 to 255) |
| `burst_clicks` | `1` | Clicks per burst |
| `burst_pause` | `1000` | Milliseconds between clicks inside a burst |
| `max_clicks` | `0` | Stop after this many clicks; `0` = no limit |
| `auto_stop_minutes` | `0` | Stop after this many minutes; `0` = off |
| `enable_failsafe` | `true` | Corner failsafe |
| `pause_when_unfocused` | `false` | Pause while the starting window isn't in front |
| `start_delay_seconds` | `3` | Countdown before a Start-button or tray start, 0 to 60; `0` = start at once. Hotkey starts are immediate |
| `max_cps_ceiling` | `50` | Runaway guard (Safety, Speed limit): most button presses allowed in one second, up to 10 000; `0` = off |
| `theme` | `"light"` | `"light"` or `"dark"` |
| `minimize_to_tray` | `true` | Minimizing hides the window to the tray icon |
| `check_for_updates` | `null` | Asked once on first launch; `true` checks GitHub for a newer release at most once a day (App) |
| `last_update_check` | `0` | When the last update check ran (Unix time) |
| `hotkeys` | `{"start": "F6", "stop": "F7", "emergency": "Esc", "toggle": ""}` | Key per action, e.g. `"Ctrl+Shift+F6"`; `""` leaves it unbound |
| `presets` | `{}` | Named profiles: `{"Name": {"x": 800, "y": 600, "interval": 100, "mouse_button": "right", ...}}`. Besides the point, a profile may hold `target_mode`, `interval`, `interval_unit`, `variation`, `mouse_button`, `click_type`, `burst_clicks`, `burst_pause`, `max_clicks`, `auto_stop_minutes`, `sequence`, `sequence_repeat`, `action`, `hold_ms`, `key`, the `condition_*` settings and, for image profiles, `image_path`, `image_region` and `image_margin`. Exported files carry an image profile's picture inside the file (`image_png`), never a path; importing saves it under `images\`. Older point-only presets still load |

**Network:** the app makes no network requests unless you allow the update check (asked once on first launch, changeable under App). Then, at most once a day, it reads `api.github.com/repos/TMHSDigital/autoclicker/releases/latest` and shows an **Update** button if a newer version exists. Nothing is downloaded or installed automatically.

An `autoclicker_settings.json` left next to the app by older versions is migrated into AppData once, automatically. If the file can't be read (say, after a hand edit with a typo), the app starts with defaults and keeps the broken file as `autoclicker_settings.json.corrupt-<time>` so you can fix and restore it.

</details>

## Troubleshooting

<details>
<summary><b>Nothing happens when I press Start</b></summary>

<br />

A dialog lists any field that failed validation. Check that the coordinates are on one of your screens and that ± variation is smaller than the interval. If no dialog appears, look at the last lines of `%APPDATA%\WindowsAutoclicker\autoclicker.log`.

</details>

<details>
<summary><b>It stops after a few clicks</b></summary>

<br />

Check the status bar and `sessions.log` for the reason: a click or time limit in **Safety**, the corner failsafe (did the cursor touch a corner?), the runaway guard (a 0 ms interval with large bursts can pass 50 clicks per second; raise **Safety, Speed limit** if that speed is intended), or **Pause when unfocused** if another window came to the front.

</details>

<details>
<summary><b>My antivirus flags or deletes the download</b></summary>

<br />

Some antivirus engines flag programs like this one even when they are clean. Two things trigger it: the exe is a PyInstaller bundle (a Python app packed into one file), and it isn't code-signed yet. Tools that move the mouse also look suspicious to heuristics. To check your copy before you allow it:

1. Compare its SHA-256 with the `.sha256` file on the [release page](https://github.com/TMHSDigital/autoclicker/releases/latest): in PowerShell, `Get-FileHash .\WindowsAutoclicker.exe`.
2. Check the build provenance with `gh attestation verify .\WindowsAutoclicker.exe --repo TMHSDigital/autoclicker`, which proves it was built by this repository's CI from a specific commit ([details](docs/RELEASING.md#verifying-a-download)).
3. Optionally look the hash up on [VirusTotal](https://www.virustotal.com/) to see what other engines say.

If it matches, restore it from quarantine and add an exclusion, and please report the false positive to your vendor (for Microsoft Defender: [submit a file](https://www.microsoft.com/en-us/wdsi/filesubmission) as "incorrectly detected"). Each report helps the next person. You can also [run from source](#run-from-source) instead.

</details>

<details>
<summary><b>Image mode never finds the image</b></summary>

<br />

Matching is exact, pixel for pixel, so anything that changes how the button is drawn stops it matching:

- **Display scaling or resolution changed**, or the window moved to a monitor with a different scale: capture again.
- **Hover, focus or pressed states**: capture the button the way it looks when the cursor is *not* on it, and remember the cursor rests on it after a click.
- **Animations, blinking cursors, HDR, Night light or color filters** change pixels from moment to moment: capture a still part of the button, such as its label.
- **The window moved** further than the search margin: raise **Search margin** (no recapture needed; it applies at the next Start), or move the window back.

The status bar says *Paused: waiting for the captured image to appear* while it looks. A run whose screen grabs keep failing stops with an error instead of waiting forever.

</details>

<details>
<summary><b>Clicks don't register in one particular app</b></summary>

<br />

If that app runs as administrator, Windows blocks input from non-elevated programs; run the autoclicker as administrator as well. Some games ignore synthetic input entirely, and fast intervals may be faster than an app can react to, so try a longer interval.

</details>

<details>
<summary><b>The hotkeys don't respond</b></summary>

<br />

Another program may already own the key; the status bar names any key that could not be registered. Pick a different one under **App → Hotkeys…**. Hotkeys also don't reach the app while an elevated (admin) window has focus unless the autoclicker runs as administrator too.

</details>

<p align="center"><sub>Still stuck? Click <b>Info</b>, then <b>Copy diagnostics</b>, and paste it into a <a href="https://github.com/TMHSDigital/autoclicker/issues/new/choose">new issue</a>. It shows you exactly what is copied, and leaves out profile names, sequence points, the watched pixel, the captured image and your Windows user folder.</sub></p>

## Contributing

Bug reports, fixes and docs improvements are welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md) and the [open issues](https://github.com/TMHSDigital/autoclicker/issues).

```bash
tasks.bat install   # .venv + pinned deps + dev tools   (make install in Git Bash)
tasks.bat check     # ruff, mypy and pytest             (make check)
```

<table>
  <tr>
    <td width="50%" valign="top">
      <b><a href="docs/ARCHITECTURE.md">Architecture →</a></b><br />
      Threads, the start/stop paths and why they differ, and where state lives.
    </td>
    <td width="50%" valign="top">
      <b><a href="docs/PERFORMANCE.md">Performance →</a></b><br />
      Hot-path measurements and the soak and profiling scripts.
    </td>
  </tr>
</table>

Releases are cut by pushing a `vX.Y.Z` tag; CI tests on Python 3.10 to 3.14, builds the executable and publishes it. See the [changelog](CHANGELOG.md).

<br />

<div align="center">

---

**[CC BY-NC 4.0](LICENSE)**: free to use, share and adapt for non-commercial purposes with attribution.<br />
For commercial licensing, contact [TM Hospitality Strategies](mailto:info@tmhsdigital.com).

<sub>Built by <a href="https://github.com/TMHSDigital">TMHSDigital</a> · <a href="https://tmhsdigital.github.io/autoclicker/">Website</a> · <a href="https://github.com/sponsors/TMHSDigital">Sponsor</a> · <a href="SECURITY.md">Security</a> · Provided as is, without warranty.</sub>

</div>
