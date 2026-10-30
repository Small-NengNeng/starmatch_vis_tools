# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

project_root = Path(SPECPATH)
a = Analysis(
    [str(project_root / "star_web_app.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[(str(project_root / "star_viewer.html"), ".")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="star_web_app", debug=False, strip=False, upx=False, console=True,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="star_web_app")
