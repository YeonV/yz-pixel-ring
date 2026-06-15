#!/usr/bin/env python
"""Build a self-contained yz-pixel-ring binary with PyInstaller.

Wraps the two build steps into one command:

    uv run --extra build python tools/build_exe.py            # daemon only
    uv run --extra build python tools/build_exe.py --with-ui  # build UI too

Env knobs are forwarded to the spec: YZ_CONSOLE=0 (no console window),
YZ_ONEDIR=1 (folder instead of single file). The result lands in ./dist/.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _run(cmd, cwd=None):
    print(f"$ {' '.join(map(str, cmd))}")
    subprocess.run(cmd, cwd=cwd, check=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--with-ui", action="store_true",
                    help="run `npm run build:pages` before bundling")
    args = ap.parse_args()

    if args.with_ui:
        npm = shutil.which("npm")
        if not npm:
            print("npm not found on PATH — install Node 18+ or drop --with-ui "
                  "(then build the UI manually).", file=sys.stderr)
            return 2
        _run([npm, "install"], cwd=ROOT / "ui")
        _run([npm, "run", "build:pages"], cwd=ROOT / "ui")

    if not (ROOT / "yz_pixel_ring" / "_ui").is_dir():
        print("note: yz_pixel_ring/_ui missing — binary will have the API/daemon but no "
              "web UI. Use --with-ui (or build it once) to include it.", file=sys.stderr)

    _run([sys.executable, "-m", "PyInstaller", "--noconfirm", "yz-pixel-ring.spec"],
         cwd=ROOT)
    out = ROOT / "dist"
    print(f"\nDone. Binary in: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
