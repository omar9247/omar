import ast
import importlib.util
import json
import sys
import tarfile
import types
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "games" / "lunar_arcade_hub"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bundle = load_module("build_game_bundle", ROOT / "tools" / "build_game_bundle.py")
exporter = load_module("aura_export", SOURCE / "core" / "aura_export.py")
previous_config = sys.modules.get("config")
sys.modules["config"] = load_module("game_config", SOURCE / "config.py")
try:
    database = load_module("game_database", SOURCE / "core" / "database.py")
finally:
    if previous_config is None:
        sys.modules.pop("config", None)
    else:
        sys.modules["config"] = previous_config


def archive_contents(tar_path, apk_path):
    with tarfile.open(tar_path, "r:gz") as archive:
        tar = {item.name: archive.extractfile(item).read()
               for item in archive.getmembers() if item.isfile()}
    with zipfile.ZipFile(apk_path) as archive:
        apk = {item.filename: archive.read(item.filename)
               for item in archive.infolist()}
    return tar, apk


def test_archives_have_identical_sorted_content(tmp_path):
    tar_path, apk_path = bundle.build_bundle(SOURCE, tmp_path)
    tar, apk = archive_contents(tar_path, apk_path)
    assert list(tar) == sorted(tar)
    assert list(apk) == sorted(apk)
    assert tar == apk
    assert "assets/core/aura_export.py" in tar
    assert "assets/games/lunar_alien_reaction.py" in tar
    assert all("__pycache__" not in name and not name.endswith(".pyc")
               for name in tar)


def test_archive_rebuild_is_byte_deterministic(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    bundle.build_bundle(SOURCE, first)
    bundle.build_bundle(SOURCE, second)
    assert (first / "lunar_arcade_hub.tar.gz").read_bytes() == \
        (second / "lunar_arcade_hub.tar.gz").read_bytes()
    assert (first / "lunar_arcade_hub.apk").read_bytes() == \
        (second / "lunar_arcade_hub.apk").read_bytes()


def test_crew_keys_are_namespaced_only_for_query_crews():
    assert database._key_for_query("lunar_arcade_hub_db_v1", "") == \
        "lunar_arcade_hub_db_v1"
    assert database._key_for_query("lunar_arcade_hub_db_v1", "?crew=cm-1") == \
        "lunar_arcade_hub_db_v1:crew:cm-1"
    assert database._key_for_query("lunar_arcade_hub_db_v1", "?crew=cm%2F1") == \
        "lunar_arcade_hub_db_v1:crew:!invalid"
    assert database._key_for_query("lunar_arcade_hub_db_v1", "?mode=standalone") == \
        "lunar_arcade_hub_db_v1"
    for crew in ("-crew", "_crew", "invalid"):
        assert database._key_for_query("db", f"?crew={crew}") == f"db:crew:{crew}"
    assert database._key_for_query("db", "?crew=%20cm1") == "db:crew:!invalid"


def test_export_payload_is_performance_only_and_callback_runs_once(monkeypatch):
    calls = []
    fake_platform = types.ModuleType("platform")
    fake_platform.window = types.SimpleNamespace(
        auraGameSession=lambda encoded: calls.append(encoded))
    monkeypatch.setitem(sys.modules, "platform", fake_platform)
    monkeypatch.setattr(sys, "platform", "emscripten")

    result = {
        "score": 42,
        "accuracy": 87.5,
        "mistakes": 2,
        "hits": 8,
        "avg_reaction_ms": float("nan"),
        "duration": 12.0,
        "stats": [("Score", "42")],
        "extra": {"difficulty": "hard", "nonfinite": float("inf")},
        "assessment": {"level": "red"},
        "feedback": {"message": "do not export"},
        "physiology": {"hrv": 1},
        "wellbeing": {"mood": 1},
    }
    assert exporter.send_session("reaction_test", "hard", result)
    assert len(calls) == 1
    payload = json.loads(calls[0])
    assert payload["game_id"] == "reaction_test"
    assert payload["difficulty"] == "hard"
    assert set(payload["result"]) == {
        "score", "accuracy", "mistakes", "hits", "avg_reaction_ms",
        "duration", "stats", "extra",
    }
    assert payload["result"]["avg_reaction_ms"] is None
    assert payload["result"]["extra"]["nonfinite"] is None
    assert "assessment" not in payload["result"]
    assert "feedback" not in payload["result"]
    assert "physiology" not in payload["result"]
    assert "wellbeing" not in payload["result"]


def test_finish_hook_exports_once_after_persistence_before_saved_flag():
    source = (SOURCE / "core" / "game_manager.py").read_text()
    tree = ast.parse(source)
    method = next(node for node in ast.walk(tree)
                  if isinstance(node, ast.FunctionDef)
                  and node.name == "_save_if_finished")
    export_calls = [node for node in ast.walk(method)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "_export_session_safely"]
    assert len(export_calls) == 1
    saved_assignments = [node for node in ast.walk(method)
                         if isinstance(node, ast.Assign)
                         and any(isinstance(target, ast.Attribute)
                                 and target.attr == "saved"
                                 for target in node.targets)]
    assert len(saved_assignments) == 1
    assert export_calls[0].lineno < saved_assignments[0].lineno
    assert "game.assessment = ev" in source
    assert "_export_session_safely(game.game_id, difficulty, result)" in source
