# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


project_root = Path(SPECPATH).resolve()
src_root = project_root / "src"
extension_dir = src_root / "gulp_cli" / "extension"

datas = [
    (str(path), "gulp_cli/extension")
    for path in sorted(extension_dir.glob("*.py"))
]

hiddenimports = [
    "gulp_cli.extension_helpers",
    *collect_submodules("gulp_cli.extension"),
]

excludes = [
    "aiohttp",
    "botocore",
    "Crypto",
    "gulp",
    "IPython",
    "jedi",
    "llvmlite",
    "lxml",
    "numba",
    "numpy",
    "orjson",
    "pandas",
    "PIL",
    "psycopg",
    "psycopg_binary",
    "psycopg_pool",
    "pytest",
    "redis",
    "scipy",
    "sqlalchemy",
    "tkinter",
    "yaml",
]


a = Analysis(
    [str(src_root / "gulp_cli" / "__main__.py")],
    pathex=[str(src_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="gulp-cli",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="gulp-cli",
)