# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置 · Token 价格追踪

产物是单文件可执行：
  macOS / Linux  ./llmcost
  Windows        llmcost.exe

双击（或直接运行）就是起服务 + 开浏览器，命令行参数照旧（--serve / --snapshot / --json）。
数据和代码本来就分家：可执行文件只带代码与种子价目，用户数据仍在 LLMCOST_DIR。
"""

import os

ROOT = os.path.dirname(SPECPATH)

datas = [
    (os.path.join(ROOT, "llmcost_ui.html"), "."),
    (os.path.join(ROOT, "plugin.json"), "."),
    (os.path.join(ROOT, "kit"), "kit"),
    (os.path.join(ROOT, "seed"), "seed"),
]

a = Analysis(
    [os.path.join(ROOT, "llmcost.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    # 纯标准库项目，把这些大件排除掉能省 20 MB 左右
    excludes=[
        "tkinter", "unittest", "pydoc", "doctest", "test",
        "numpy", "pandas", "matplotlib", "scipy", "PIL", "setuptools", "pip",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="llmcost",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
