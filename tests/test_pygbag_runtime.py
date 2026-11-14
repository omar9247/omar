import hashlib
import json
import re
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "web" / "static" / "lunar-arcade-hub" / "runtime"
INDEX = ROOT / "web" / "static" / "lunar-arcade-hub" / "index.html"
PACKAGE_INDEX = RUNTIME / "index-0.9.3-cp312.json"
PYGAME_WHEEL = RUNTIME / "cp312" / "pygame_ce-2.5.7-cp312-cp312-wasm32_bi_emscripten.whl"


def test_pinned_runtime_manifest_and_loader_are_local_only():
    manifest = json.loads((RUNTIME / "SOURCES.json").read_text())
    assert manifest["runtime"] == "Pygbag 0.9.3 / CPython 3.12"
    assert manifest["files"]

    for item in manifest["files"]:
        path = RUNTIME / item["path"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert path.is_file()
        assert path.stat().st_size == item["bytes"]
        assert digest == item["sha256"]
        assert item["source"].startswith("https://pygame-web.github.io/cdn/")

    html = INDEX.read_text()
    assert 'src="runtime/pythons.js"' in html
    assert 'cdn : "runtime/"' in html
    assert 'data-os="snd,gui"' in html
    assert not re.search(r"https?://", html)
    assert "browserfs.min.js" not in html
    assert 'src="about:blank"' in html

    cpythonrc = (RUNTIME / "cpythonrc.py").read_text()
    assert "http://localhost:<port>" not in cpythonrc
    assert 'PYCONFIG_PKG_INDEXES = ["runtime/"]' in cpythonrc
    assert 'PYCONFIG_PKG_INDEXES_DEV = ["runtime/"]' in cpythonrc
    assert "aio.pep0723.Config.PKG_BASE_DEFAULT = PYCONFIG_PKG_INDEXES[0]" in cpythonrc
    override = "aio.pep0723.Config.PKG_INDEXES = PyConfig.pkg_indexes"
    assert override in cpythonrc
    assert cpythonrc.index(override) < cpythonrc.index("    import aio.toplevel")

    package_index = json.loads(PACKAGE_INDEX.read_text())
    assert package_index["-CDN-"] == "runtime/"
    assert package_index["pygame"] == "cp312/pygame_ce-2.5.7-<abi>-<abi>-<api>.whl"
    assert not re.search(r"https?://", package_index["-CDN-"])

    with zipfile.ZipFile(PYGAME_WHEEL) as wheel:
        assert "pygame/__init__.py" in wheel.namelist()
        assert "pygame/base.cpython-312-wasm32-emscripten.so" in wheel.namelist()
