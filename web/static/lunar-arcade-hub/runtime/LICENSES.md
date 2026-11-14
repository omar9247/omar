# Vendored runtime notices

The browser runtime is pinned to Pygbag 0.9.3 / CPython 3.12 with the pygame-ce 2.5.7 WASM wheel. Source URLs, SHA-256 checksums and the local package-index/bootstrap transforms are recorded in [`SOURCES.json`](SOURCES.json).

- **Pygbag loader/glue:** MIT, copyright pygame-web. Full notice: [pygbag-MIT.txt](licenses/pygbag-MIT.txt); upstream <https://github.com/pygame-web/pygbag/blob/main/LICENSE>.
- **CPython runtime:** Python Software Foundation License 2.0 and historical notices. Full text: [CPython-LICENSE.txt](licenses/CPython-LICENSE.txt); upstream <https://github.com/python/cpython/blob/3.12/LICENSE>.
- **pygame-ce WASM wheel/runtime:** LGPL-2.1-or-later. Full text: [pygame-ce-LGPL-2.1.txt](licenses/pygame-ce-LGPL-2.1.txt); upstream <https://github.com/pygame-community/pygame-ce/blob/main/docs/LGPL.txt>. The wheel is unmodified; only Pygbag glue and package-index configuration were redirected locally.

Runtime source/build provenance is available from <https://github.com/pygame-web/archives> and <https://github.com/pygame-community/pygame-ce>. The pygame native module is dynamically loaded from the local wheel, not folded into the application's source bundle. Keep notices with redistributed runtime files and preserve users' ability to replace the library with an interface-compatible build.

Game source and gameplay assets remain under `games/lunar_arcade_hub/` and are packaged by the existing deterministic bundle builder. This vendoring changes runtime asset delivery, not game scoring, timing, artwork or health interpretation.
