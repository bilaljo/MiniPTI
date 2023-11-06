# -*- mode: python ; coding: utf-8 -*-

added_files = [
         ( 'minipti/hardware', 'minipti/hardware' ),
         ( 'minipti/algorithm', 'minipti/algorithm' ),
         ( 'minipti/gui', 'minipti/gui' ),
         ]


a = Analysis(
    ['minipti\\__main__.py'],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=[],
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
    name='MiniPTI',
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
    icon=['minipti\\gui\\images\\logo.ico'],
)
