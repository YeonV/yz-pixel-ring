#!/usr/bin/env python
"""Cut a release: bump the version, commit "Release X.Y.Z", and push — which
triggers the GitHub Actions "Builder" workflow (binaries + IIFE + wheel + PyPI).

    python tools/release.py            # patch bump (0.2.1 -> 0.2.2) + push
    python tools/release.py --minor    # 0.2.1 -> 0.3.0
    python tools/release.py --major    # 0.2.1 -> 1.0.0
    python tools/release.py --set 1.2.3
    python tools/release.py --no-push  # bump + commit only (push yourself later)

Cross-platform: pure Python, needs only `git` and `uv` on PATH. Bumps the version
in pyproject.toml, ui/package.json and yz_pixel_ring/__init__.py, refreshes uv.lock,
then commits exactly those files (a clean working tree is required first, so the
Release commit contains only the bump).
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
PKG_INIT = ROOT / "yz_pixel_ring" / "__init__.py"
UI_PKG = ROOT / "ui" / "package.json"
LOCK = ROOT / "uv.lock"


def run(*cmd):
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def read_version() -> str:
    m = re.search(r'^version = "(.+?)"', PYPROJECT.read_text(encoding="utf-8"), re.M)
    if not m:
        sys.exit("could not find version in pyproject.toml")
    return m.group(1)


def bump(v: str, part: str) -> str:
    try:
        major, minor, patch = (int(x) for x in v.split("."))
    except ValueError:
        sys.exit(f"current version {v!r} is not X.Y.Z")
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def replace(path: Path, pattern: str, repl: str) -> None:
    text = path.read_text(encoding="utf-8")
    new, n = re.subn(pattern, repl, text, count=1, flags=re.M)
    if n != 1:
        sys.exit(f"version line not found in {path.relative_to(ROOT)}")
    path.write_text(new, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    grp = ap.add_mutually_exclusive_group()
    grp.add_argument("--minor", action="store_const", const="minor", dest="part")
    grp.add_argument("--major", action="store_const", const="major", dest="part")
    grp.add_argument("--set", dest="explicit", metavar="X.Y.Z", help="set an exact version")
    ap.add_argument("--no-push", action="store_true", help="commit only; don't push")
    ap.set_defaults(part="patch")
    args = ap.parse_args()

    # Require a clean tree so the Release commit is ONLY the version bump.
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                           capture_output=True, text=True).stdout.strip()
    if dirty:
        sys.exit("working tree is dirty — commit or stash first:\n" + dirty)

    cur = read_version()
    new = args.explicit or bump(cur, args.part)
    if not re.fullmatch(r"\d+\.\d+\.\d+", new):
        sys.exit(f"invalid version: {new!r} (expected X.Y.Z)")
    if new == cur:
        sys.exit(f"version is already {new}")
    print(f"version: {cur} -> {new}")

    replace(PYPROJECT, r'^version = ".+?"', f'version = "{new}"')
    replace(PKG_INIT, r'^__version__ = ".+?"', f'__version__ = "{new}"')
    replace(UI_PKG, r'^(\s*"version": )".+?"', rf'\g<1>"{new}"')
    run("uv", "lock")

    run("git", "add", str(PYPROJECT), str(LOCK), str(PKG_INIT), str(UI_PKG))
    run("git", "commit", "-m", f"Release {new}")
    if args.no_push:
        print(f"\nCommitted 'Release {new}'. Push when ready:  git push")
    else:
        run("git", "push")
        print(f"\nReleased {new}. GitHub Actions 'Builder' is building "
              "(binaries + IIFE + wheel + PyPI).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
