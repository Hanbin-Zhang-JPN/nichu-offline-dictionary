#!/usr/bin/env python3
"""Create an offline ZIP including the verified, prebuilt SQLite index."""

import argparse
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nichu import __version__
from nichu.build import ensure_database, sha256
from nichu.text import ROOT


def package(version):
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("版本应为 x.y.z")
    ensure_database()
    destination = ROOT / "dist"
    destination.mkdir(exist_ok=True)
    prefix = f"nichu-offline-dictionary-{version}"
    archive = destination / f"{prefix}.zip"
    directories = {"nichu", "web", "scripts", "tests", "docs", "data", "licenses", ".github"}
    root_files = {"README.md", "LICENSE", "DATA_LICENSE.md", "CONTRIBUTING.md", "start.command", "start.bat", ".gitignore", ".gitattributes"}
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zipped:
        for path in sorted(ROOT.rglob("*")):
            relative = path.relative_to(ROOT)
            if path.is_symlink() or not path.is_file() or "__pycache__" in relative.parts:
                continue
            if relative.parts[0] not in directories and str(relative) not in root_files:
                continue
            if path.suffix in {".tmp", ".pyc", ".pyo"} or path.name.endswith(("-journal", "-wal", "-shm")):
                continue
            zipped.write(path, prefix + "/" + relative.as_posix())
    (destination / "SHA256SUMS").write_text(f"{sha256(archive)}  {archive.name}\n", encoding="utf-8")
    print(f"{archive} ({archive.stat().st_size / 1024**2:.1f} MiB)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default=__version__)
    package(parser.parse_args().version)
