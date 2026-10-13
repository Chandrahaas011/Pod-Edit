# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules
from pathlib import Path

source_fingerprint = Path(SPECPATH) / 'build' / 'source-fingerprint.json'
if not source_fingerprint.is_file():
    raise SystemExit('Run packaging/fingerprint_sources.py immediately before freezing.')
datas = [(str(source_fingerprint), '.')]
binaries = []
hiddenimports = ['sklearn.cluster']
for package in ('pyannote.audio',):
    datas += collect_data_files(package, include_py_files=False)
    binaries += collect_dynamic_libs(package)
    hiddenimports += collect_submodules(package)
# SpeechBrain's lazy_export_all scans its installed package tree at runtime;
# these sources are required runtime metadata, not application-source leakage.
datas += collect_data_files('speechbrain', include_py_files=True)
binaries += collect_dynamic_libs('speechbrain')
hiddenimports += collect_submodules('speechbrain')


a = Analysis(
    ['../main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'tensorboardX', 'librosa', 'numba', 'llvmlite',
              'audioread', 'torchcodec'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PodEdit.Engine',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PodEdit.Engine',
)
