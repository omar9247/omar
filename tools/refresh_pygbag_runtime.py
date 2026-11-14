#!/usr/bin/env python3
"""Refresh or verify the self-hosted Pygbag 0.9.3 / CPython 3.12 runtime.

The default source URLs and source hashes are intentionally pinned. A refresh
fails closed when upstream bytes change; update this file and SOURCES.json in a
reviewed dependency update rather than silently accepting a new runtime.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "web" / "static" / "lunar-arcade-hub" / "runtime"
SOURCES = RUNTIME / "SOURCES.json"
PINNED = {
    "pythons.js": ("https://pygame-web.github.io/cdn/0.9.3/pythons.js", "6da43e3e62c3db933421b99681e8ef99ed9b0ce1589ed8a0c69b88443278e019"),
    "cpythonrc.py": ("https://pygame-web.github.io/cdn/0.9.3/cpythonrc.py", "b8a0b8168b58ef7c38c17d4705c9cbe1751fa667a0a6d26ed26f0537134735de"),
    "empty.ogg": ("https://pygame-web.github.io/cdn/0.9.3/empty.ogg", "884c20d864222b845aa78fb078ec370f4ddaa203cd92ace28440ed7733403b40"),
    "cpython312/main.js": ("https://pygame-web.github.io/cdn/0.9.3/cpython312/main.js", "01c4e4dc7145a482ad259d8272ce73d97b58ec2a141bfb57e620347730d159c7"),
    "cpython312/main.data": ("https://pygame-web.github.io/cdn/0.9.3/cpython312/main.data", "b068df4d59b06b113cfc3c4d6419bdf699d2c2eeb547c9119e2044c98cdc4a59"),
    "cpython312/main.wasm": ("https://pygame-web.github.io/cdn/0.9.3/cpython312/main.wasm", "3cfb882de90feeb367325f0c58731932880c8f424fb5a670b98d035ae862b280"),
    "index-0.9.3-cp312.json": ("https://pygame-web.github.io/cdn/index-0.9.3-cp312.json", "ec6edacc1b95700c99b8daecb8ce3949e58e96a1da5234c81d8a0071aa537213"),
    "cp312/pygame_ce-2.5.7-cp312-cp312-wasm32_bi_emscripten.whl": (
        "https://pygame-web.github.io/cdn/cp312/pygame_ce-2.5.7-cp312-cp312-wasm32_bi_emscripten.whl",
        "4f2caa3020592950565f3649c41e2eeacd001be93da892d60e5a4a43d893a323",
    ),
}
TRANSFORMED = {"cpythonrc.py", "index-0.9.3-cp312.json"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_local() -> None:
    manifest = json.loads(SOURCES.read_text())
    by_path = {item["path"]: item for item in manifest["files"]}
    for path, (_, source_hash) in PINNED.items():
        local = RUNTIME / path
        if not local.is_file():
            raise SystemExit(f"missing vendored runtime file: {local}")
        expected = by_path[path]["sha256"]
        actual = sha256(local)
        if actual != expected:
            raise SystemExit(f"checksum mismatch: {path}: {actual} != {expected}")
        if path in TRANSFORMED:
            continue
        if source_hash != expected:
            raise SystemExit(f"manifest source/local hash mismatch: {path}")
    cpythonrc = (RUNTIME / "cpythonrc.py").read_text()
    if 'PYCONFIG_PKG_INDEXES = ["runtime/"]' not in cpythonrc or 'PYCONFIG_PKG_INDEXES_DEV = ["runtime/"]' not in cpythonrc:
        raise SystemExit("runtime package indexes are not local")
    index = json.loads((RUNTIME / "index-0.9.3-cp312.json").read_text())
    if index.get("-CDN-") != "runtime/" or index.get("pygame") != "cp312/pygame_ce-2.5.7-<abi>-<abi>-<api>.whl":
        raise SystemExit("local package index is not redirected to the pinned pygame wheel")
    print(f"verified {len(PINNED)} pinned runtime files")


def refresh() -> None:
    with tempfile.TemporaryDirectory(prefix="pygbag-runtime-") as directory:
        staging = Path(directory)
        for relative, (url, expected) in PINNED.items():
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with urlopen(url, timeout=120) as response, target.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            if sha256(target) != expected:
                raise SystemExit(f"upstream checksum changed: {relative}; review and repin explicitly")
        cpythonrc = staging / "cpythonrc.py"
        text = cpythonrc.read_text()
        text = text.replace(
            'PYCONFIG_PKG_INDEXES_DEV = ["http://localhost:<port>/cdn/"]',
            'PYCONFIG_PKG_INDEXES = ["runtime/"]\nPYCONFIG_PKG_INDEXES_DEV = ["runtime/"]',
        )
        text = text.replace(
            "        if (PyConfig.dev_mode > 0) or PyConfig.pygbag:\n            # in pygbag dev mode use local repo",
            "        PyConfig.pkg_indexes = PYCONFIG_PKG_INDEXES\n        if (PyConfig.dev_mode > 0) or PyConfig.pygbag:\n            # in pygbag dev mode use local repo",
        )
        text = text.replace(
            "        # now in pep0723\n        #        else:\n        #            # address cdn\n        #            PyConfig.pkg_indexes = PYCONFIG_PKG_INDEXES\n",
            "",
        )
        text = text.replace(
            "    import aio.toplevel\n",
            "    import aio.pep0723\n"
            "    aio.pep0723.Config.PKG_BASE_DEFAULT = PYCONFIG_PKG_INDEXES[0]\n"
            "    aio.pep0723.Config.PKG_INDEXES = PyConfig.pkg_indexes\n"
            "    import aio.toplevel\n",
        )
        cpythonrc.write_text(text)
        index = staging / "index-0.9.3-cp312.json"
        text = index.read_text()
        text = text.replace('"https://pygame-web.github.io/cdn/"', '"runtime/"', 1)
        index.write_text(text)
        for relative in PINNED:
            destination = RUNTIME / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((staging / relative).read_bytes())
    verify_local()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="download the pinned upstream bytes")
    args = parser.parse_args()
    refresh() if args.refresh else verify_local()
