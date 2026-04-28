# PyInstaller spec for `vista`.
#
# Build with:
#     pyinstaller --clean --noconfirm vista.spec
#
# Produces a directory at `dist/vista/` containing the `vista` launcher
# plus all bundled dependencies. Tar that directory for distribution:
#     tar -cJf vista-${PLATFORM}-${ARCH}.tar.xz -C dist vista
#
# We use --onedir (not --onefile) for two reasons:
#   1. Zero startup tax. --onefile extracts to a temp dir on every
#      invocation (~200 ms), which is felt when typing `vista routine X`
#      in a tight loop. --onedir loads instantly.
#   2. Easier signing on macOS — Gatekeeper-friendly bundle layout.

# ruff: noqa: F821
# (PyInstaller spec files are exec'd with `Analysis`, `EXE`, etc.
# injected as builtins; ruff doesn't see them defined.)

from pathlib import Path

block_cipher = None
project_root = Path(SPECPATH).resolve()

a = Analysis(
    [str(project_root / "src/vista_cli/__main__.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    # Ship the canonical packages.csv that lives inside the wheel.
    datas=[
        (str(project_root / "src/vista_cli/data"), "vista_cli/data"),
    ],
    hiddenimports=[
        # Click discovers commands eagerly; nothing dynamic to add.
        # Keep this list explicit anyway — easier to debug a missing
        # import than to wonder why a subcommand crashes.
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # Trim things PyInstaller pulls in by default that vista-cli
        # never uses. Each entry shaves ~MB off the bundle.
        "tkinter",
        "test",
        "unittest",
        "pydoc",
        "doctest",
        "lib2to3",
        "xml.dom",
        "xml.sax",
    ],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="vista",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # UPX trips macOS Gatekeeper; not worth the size win.
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,    # let PyInstaller pick host arch (or universal2 via --target-arch)
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="vista",
)
