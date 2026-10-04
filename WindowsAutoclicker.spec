# -*- mode: python ; coding: utf-8 -*-
"""Frozen Windows build. Icons ship in autoclicker/assets (regenerate with create_icon.py)."""

import re
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

# Version resource so the exe's Properties > Details show the product and version.
_version = re.search(
    r'^__version__ = "([^"]+)"', Path("autoclicker/__init__.py").read_text("utf-8"), re.M
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

a = Analysis(
    ["autoclicker.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("autoclicker/assets/autoclicker.ico", "autoclicker/assets"),
        ("autoclicker/assets/autoclicker.png", "autoclicker/assets"),
    ],
    hiddenimports=["sv_ttk"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    icon="autoclicker/assets/autoclicker.ico",
    version=version_info,
)
