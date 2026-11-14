#!/usr/bin/env python3
"""Build deterministic Lunar Arcade Hub TAR.GZ and APK archives."""
from __future__ import annotations

import argparse
import gzip
import io
import tarfile
import zipfile
from pathlib import Path


ARCHIVE_BASENAME = "lunar_arcade_hub"
_FIXED_DATE = (1980, 1, 1, 0, 0, 0)


def _files(source: Path):
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        yield path


def _archive_name(source: Path, path: Path) -> str:
    return (Path("assets") / path.relative_to(source)).as_posix()


def build_tar(source: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w", format=tarfile.USTAR_FORMAT) as archive:
                for path in _files(source):
                    info = tarfile.TarInfo(_archive_name(source, path))
                    data = path.read_bytes()
                    info.size = len(data)
                    info.mode = 0o644
                    info.mtime = 0
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    archive.addfile(info, io.BytesIO(data))


def build_apk(source: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as archive:
        for path in _files(source):
            info = zipfile.ZipInfo(_archive_name(source, path), _FIXED_DATE)
            info.create_system = 3
            info.create_version = 20
            info.extract_version = 20
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())


def build_bundle(source: Path, output_dir: Path) -> tuple[Path, Path]:
    source = source.resolve()
    output_dir = output_dir.resolve()
    tar_path = output_dir / f"{ARCHIVE_BASENAME}.tar.gz"
    apk_path = output_dir / f"{ARCHIVE_BASENAME}.apk"
    build_tar(source, tar_path)
    build_apk(source, apk_path)
    return tar_path, apk_path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path,
                        default=root / "games" / "lunar_arcade_hub")
    parser.add_argument("--output-dir", type=Path,
                        default=root / "web" / "static" / "lunar-arcade-hub")
    args = parser.parse_args()
    tar_path, apk_path = build_bundle(args.source, args.output_dir)
    print(tar_path)
    print(apk_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
