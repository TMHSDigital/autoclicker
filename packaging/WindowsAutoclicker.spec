# -*- mode: python ; coding: utf-8 -*-
"""Frozen Windows build. Icons ship in autoclicker/assets (regenerate with tools/create_icon.py).

Build from the repo root: pyinstaller --clean --noconfirm packaging/WindowsAutoclicker.spec
"""

import re
import runpy
from pathlib import Path

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

# Paths are relative to the repo root, one level up from this file.
ROOT = Path(SPECPATH).resolve().parent  # noqa: F821 (set by PyInstaller)

# Version resource so the exe's Properties > Details show the product and version.
_version = re.search(
    r'^__version__ = "([^"]+)"', (ROOT / "autoclicker" / "__init__.py").read_text("utf-8"), re.M
).group(1)
_parts = tuple(int(p) for p in (_version.split(".") + ["0", "0", "0"])[:4])
version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=_parts, prodvers=_parts),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040904B0",
                    [
                        StringStruct("CompanyName", "TM Hospitality Strategies"),
                        StringStruct("FileDescription", "Windows Autoclicker"),
                        StringStruct("FileVersion", _version),
                        StringStruct("InternalName", "WindowsAutoclicker"),
                        StringStruct("LegalCopyright", "CC BY-NC 4.0"),
                        StringStruct("OriginalFilename", "WindowsAutoclicker.exe"),
                        StringStruct("ProductName", "Windows Autoclicker"),
                        StringStruct("ProductVersion", _version),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [0x0409, 1200])]),
    ],
)

# License texts of the bundled packages, generated from the installed runtime
# lock on every build (#153). CI also attaches build/THIRD_PARTY_NOTICES.txt
# to each release.
_tools = runpy.run_path(str(ROOT / "tools" / "third_party_notices.py"))
_notices = _tools["write_notices"]()

a = Analysis(
    [str(ROOT / "autoclicker.py")],
    pathex=[],
    binaries=[],
    datas=[
        (str(ROOT / "autoclicker" / "assets" / "autoclicker.ico"), "autoclicker/assets"),
        (str(ROOT / "autoclicker" / "assets" / "autoclicker.png"), "autoclicker/assets"),
        (str(_notices), "."),
        (str(ROOT / "LICENSE"), "."),
    ],
    # ImageTk: image thumbnail; pyautogui: loaded through importlib (#163). Both lazy.
    hiddenimports=["sv_ttk", "PIL.ImageTk", "pyautogui"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Optional pyautogui imports the app never uses; mouseinfo and pymsgbox are
    # GPLv3+ (#153). Keep in sync with NOT_BUNDLED in tools/third_party_notices.py.
    excludes=["mouseinfo", "pymsgbox", "pyperclip"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="WindowsAutoclicker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX-packed executables are a common antivirus false-positive trigger.
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "autoclicker" / "assets" / "autoclicker.ico"),
    version=version_info,
)
