# PyInstaller spec for yz-pixel-ring — a single self-contained daemon binary
# with the web UI bundled in. Hand-maintained (not auto-generated).
#
#   1) build the UI first:   cd ui && npm install && npm run build:pages
#   2) build the binary:     uv run pyinstaller yz-pixel-ring.spec
#   -> dist/yz-pixel-ring(.exe)
#
# Onefile by default. Env knobs (optional):
#   YZ_CONSOLE=0   build with no console window (output -> ~/.yz-pixel-ring/daemon.log)
#   YZ_ONEDIR=1    build a folder instead of a single file (faster start, no AV flags)
import os
import sys

from PyInstaller.utils.hooks import collect_submodules

root = os.path.abspath(os.getcwd())
console = os.environ.get("YZ_CONSOLE", "1") != "0"
onedir = os.environ.get("YZ_ONEDIR", "0") == "1"

# App icon (regenerate from the SVG with tools/make_icon.py). Windows-only: the
# .ico matters for the .exe, and on macOS PyInstaller would try (and, without
# Pillow installed, fail) to convert it to .icns. mac/linux artifacts are bare
# CLI binaries that don't carry an icon anyway.
icon_path = os.path.join(root, "assets", "yz-pixel-ring.ico")
icon = icon_path if (os.path.isfile(icon_path) and sys.platform == "win32") else None

# Bundle the built UI (served by the daemon at http://127.0.0.1:9700/). It lives
# inside the package so the same path works for the wheel and the frozen exe.
datas = []
ui_dir = os.path.join(root, "yz_pixel_ring", "_ui")
if os.path.isdir(ui_dir):
    datas.append((ui_dir, os.path.join("yz_pixel_ring", "_ui")))
else:
    print("WARNING: yz_pixel_ring/_ui not found — building UI-less binary "
          "(run `cd ui && npm run build:pages` first to include the web UI).")

# uvicorn/starlette/websocket import submodules dynamically; pull them all in.
hiddenimports = []
for pkg in ("uvicorn", "fastapi", "starlette", "websocket"):
    hiddenimports += collect_submodules(pkg)

a = Analysis(
    [os.path.join("packaging", "run_daemon.py")],
    pathex=[root],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "_pytest", "numpy", "PIL"],
    noarchive=False,
)
pyz = PYZ(a.pure)

if onedir:
    exe = EXE(
        pyz, a.scripts, [], exclude_binaries=True,
        name="yz-pixel-ring", debug=False, strip=False, upx=True,
        console=console, icon=icon,
    )
    coll = COLLECT(
        exe, a.binaries, a.datas, strip=False, upx=True, name="yz-pixel-ring",
    )
else:
    exe = EXE(
        pyz, a.scripts, a.binaries, a.datas, [],
        name="yz-pixel-ring", debug=False, strip=False, upx=True,
        runtime_tmpdir=None, console=console, icon=icon,
    )
