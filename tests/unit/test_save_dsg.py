import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SAVE_DSG = ROOT / "scripts/save_dsg.sh"


def test_save_dsg_writes_normalized_graph_without_embedded_mesh(tmp_path):
    run_dir = tmp_path / "run"
    upstream = run_dir / "upstream"
    backend = upstream / "backend"
    frontend = upstream / "frontend"
    backend.mkdir(parents=True)
    frontend.mkdir()

    source = backend / "dsg.json"
    source.write_text('{"source_has_mesh": true}\n', encoding="utf-8")
    source_with_mesh = backend / "dsg_with_mesh.json"
    source_with_mesh.write_text(
        '{"backend_mesh": true}\n', encoding="utf-8"
    )
    (frontend / "dsg.json").write_text(
        '{"wrong_source": "frontend"}\n', encoding="utf-8"
    )
    source_mesh = backend / "mesh.ply"
    source_mesh.write_text("ply\nend_header\n", encoding="ascii")
    (frontend / "mesh.ply").write_text("wrong frontend mesh\n", encoding="ascii")

    fake_module = tmp_path / "spark_dsg.py"
    fake_module.write_text(
        """
import json


class Graph:
    def __init__(self, path):
        self.path = path

    def has_mesh(self):
        return False

    def save(self, path, include_mesh=True):
        with open(path, "w", encoding="utf-8") as stream:
            json.dump({"include_mesh": include_mesh, "source": self.path}, stream)


class DynamicSceneGraph:
    @staticmethod
    def load(path):
        return Graph(path)
""",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(tmp_path)
    result = subprocess.run(
        [str(SAVE_DSG), str(run_dir)],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    normalized = json.loads((run_dir / "dsg.json").read_text(encoding="utf-8"))
    assert normalized["include_mesh"] is False
    assert normalized["source"] == str(source)
    assert json.loads(source.read_text(encoding="utf-8"))["source_has_mesh"] is True
    assert (run_dir / "dsg_with_mesh.json").read_bytes() == source_with_mesh.read_bytes()
    assert (run_dir / "mesh.ply").read_bytes() == source_mesh.read_bytes()
    assert "Mesh-free backend DSG saved:" in result.stdout
    assert "Mesh-bearing backend DSG saved:" in result.stdout


def test_save_dsg_rejects_frontend_only_output(tmp_path):
    run_dir = tmp_path / "run"
    frontend = run_dir / "upstream/frontend"
    frontend.mkdir(parents=True)
    (frontend / "dsg.json").write_text("{}\n", encoding="utf-8")

    result = subprocess.run(
        [str(SAVE_DSG), str(run_dir)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "without a backend DSG JSON" in result.stderr
    assert not (run_dir / "dsg.json").exists()


def test_save_dsg_rejects_backend_without_mesh_json(tmp_path):
    run_dir = tmp_path / "run"
    backend = run_dir / "upstream/backend"
    backend.mkdir(parents=True)
    (backend / "dsg.json").write_text("{}\n", encoding="utf-8")

    fake_module = tmp_path / "spark_dsg.py"
    fake_module.write_text(
        """
class Graph:
    def save(self, path, include_mesh=True):
        with open(path, "w", encoding="utf-8") as stream:
            stream.write("{}\\n")
class DynamicSceneGraph:
    @staticmethod
    def load(path):
        return Graph()
""",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(tmp_path)
    result = subprocess.run(
        [str(SAVE_DSG), str(run_dir)],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 1
    assert "without a backend DSG JSON containing mesh" in result.stderr
