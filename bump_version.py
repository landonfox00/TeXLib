"""The library's version contract, and the one tool that maintains it.

The contract (see CONTRIBUTING "Releasing"):

  - texlib-manifest.json carries the released version and the core-file
    triple the installer and Doctor probe for. The git tag is authoritative;
    the manifest is its machine-readable mirror.
  - Every \\ProvidesClass/\\ProvidesPackage line in the library carries that
    same version (dates and versions had drifted per-file for eighteen months
    before this existed -- autoexam's carried no version at all).
  - The manifest version equals the newest released heading in CHANGELOG.md.

Usage:
  python bump_version.py --check          # verify the contract (CI runs this)
  python bump_version.py 0.7.3            # release bump: manifest + Provides
  python bump_version.py 0.7.3 --date 2026/09/01   # override the stamp date

quiver.sty is vendored third-party and is deliberately never touched.
"""

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "texlib-manifest.json"
CHANGELOG = ROOT / "CHANGELOG.md"
TEXLIB_PY = ROOT / "Sublime" / "texlib" / "texlib.py"
EXCLUDE = {"quiver.sty"}

PROVIDES_RE = re.compile(
    r"^(?P<head>\\Provides(?:Class|Package)\{[^}]+\}\[)"
    r"(?:\d{4}/\d{2}/\d{2})?\s*"
    r"(?:v[0-9][\w.\-]*)?\s*"
    r"(?P<desc>.*)$"
)
RELEASED_RE = re.compile(r"^## \[(\d+\.\d+\.\d+)\]")


def provides_files():
    for pattern in ("*.sty", "*.cls"):
        for path in sorted(ROOT.glob(pattern)) + sorted(ROOT.glob(f"*/{pattern}")):
            if path.name in EXCLUDE:
                continue
            yield path


def find_provides(path):
    """(line_index, match) for the file's \\Provides line, or None."""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    for i, line in enumerate(lines):
        m = PROVIDES_RE.match(line.rstrip("\n"))
        if m:
            return lines, i, m
    return None


def newest_released():
    for line in CHANGELOG.read_text(encoding="utf-8").splitlines():
        m = RELEASED_RE.match(line)
        if m:
            return m.group(1)
    return None


def core_probe_from_plugin():
    """The _CORE_LIBRARY_FILES tuple, parsed textually (texlib.py imports
    sublime at module scope, so it cannot be imported headlessly)."""
    m = re.search(r"_CORE_LIBRARY_FILES\s*=\s*\(([^)]*)\)", TEXLIB_PY.read_text(encoding="utf-8"))
    if not m:
        return None
    return [s for s in re.findall(r'"([^"]+)"', m.group(1))]


def check():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    version, failures = manifest["version"], []

    released = newest_released()
    if released != version:
        failures.append(f"manifest {version} != newest released CHANGELOG heading {released}")

    for name in manifest["core_files"]:
        if not (ROOT / name).is_file():
            failures.append(f"core file missing from repo root: {name}")

    probe = core_probe_from_plugin()
    if probe is None:
        failures.append("could not parse _CORE_LIBRARY_FILES from Sublime/texlib/texlib.py")
    elif sorted(probe) != sorted(manifest["core_files"]):
        failures.append(f"manifest core_files {manifest['core_files']} != plugin probe {probe}")

    for path in provides_files():
        found = find_provides(path)
        if found is None:
            failures.append(f"{path.relative_to(ROOT)}: no \\Provides line")
            continue
        _, _, m = found
        line = m.group(0)
        if f" v{version} " not in line and not line.rstrip("]").endswith(f"v{version}"):
            failures.append(f"{path.relative_to(ROOT)}: \\Provides does not carry v{version}: {line.strip()}")

    for f in failures:
        print(f"FAIL: {f}")
    if not failures:
        print(f"version contract OK: v{version}, {sum(1 for _ in provides_files())} \\Provides lines, "
              f"core triple matches the plugin probe")
    return 1 if failures else 0


def bump(version, date):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["version"] = version
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    for path in provides_files():
        found = find_provides(path)
        if found is None:
            print(f"WARN: {path.relative_to(ROOT)} has no \\Provides line; skipped")
            continue
        lines, i, m = found
        lines[i] = f"{m.group('head')}{date} v{version} {m.group('desc')}\n"
        path.write_text("".join(lines), encoding="utf-8")
        print(f"stamped {path.relative_to(ROOT)}")

    if newest_released() != version:
        print(f"NOTE: CHANGELOG.md has no released heading [{version}] yet -- "
              f"close the Unreleased section before tagging, or --check will fail.")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("version", nargs="?", help="release version to stamp, e.g. 0.7.3")
    ap.add_argument("--check", action="store_true", help="verify the contract instead of bumping")
    ap.add_argument("--date", default=datetime.date.today().strftime("%Y/%m/%d"),
                    help="date stamp for the Provides lines (YYYY/MM/DD, default today)")
    args = ap.parse_args()

    if args.check:
        if args.version:
            ap.error("--check takes no version argument")
        return check()
    if not args.version:
        ap.error("give a version to bump to, or --check")
    if not re.fullmatch(r"\d+\.\d+\.\d+", args.version):
        ap.error(f"version must be X.Y.Z, got {args.version!r}")
    if not re.fullmatch(r"\d{4}/\d{2}/\d{2}", args.date):
        ap.error(f"--date must be YYYY/MM/DD, got {args.date!r}")
    return bump(args.version, args.date)


if __name__ == "__main__":
    sys.exit(main())
