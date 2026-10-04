# -*- mode: python ; coding: utf-8 -*-
"""Frozen Windows build. Icons ship in autoclicker/assets (regenerate with create_icon.py)."""

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
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="autoclicker/assets/autoclicker.ico",
)
