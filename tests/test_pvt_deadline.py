import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is optional; run node tests/test_pvt_deadline.cjs")
def test_pvt_deadline():
    result = subprocess.run(["node", "tests/test_pvt_deadline.cjs"], cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
