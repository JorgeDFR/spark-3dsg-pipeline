import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("colcon_status", [0, 7])
def test_repository_tests_use_the_built_workspace(tmp_path, colcon_status):
    repository = tmp_path / "repository"
    repository.mkdir()
    workspace = tmp_path / "ros workspace"
    for directory in ("src", "build", "install"):
        (workspace / directory).mkdir(parents=True)
    commands = tmp_path / "commands"
    commands.mkdir()
    trace = tmp_path / "trace.jsonl"
    # Stub executables exercise the shell orchestration without running ROS.
    stub = f"""#!{sys.executable}
import json, os, pathlib, sys
with open(os.environ['TRACE'], 'a') as stream:
    stream.write(json.dumps([pathlib.Path(sys.argv[0]).name, os.getcwd(), sys.argv[1:]]) + '\\n')
if pathlib.Path(sys.argv[0]).name == 'colcon' and 'test' in sys.argv:
    raise SystemExit(int(os.environ['COLCON_STATUS']))
"""
    for name in ("colcon", "python3"):
        executable = commands / name
        executable.write_text(stub)
        executable.chmod(0o755)
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/shell/run_tests.sh")],
        cwd=tmp_path, capture_output=True, text=True,
        env={
            **os.environ, "PATH": f"{commands}:{os.environ['PATH']}",
            "PIPELINE_ROOT": str(repository), "ROS_WS": str(workspace),
            "TRACE": str(trace), "COLCON_STATUS": str(colcon_status),
        },
    )
    assert result.returncode == colcon_status, result.stderr
    calls = [json.loads(line) for line in trace.read_text().splitlines()]
    args = calls[0][2]
    for option, directory in (("--base-paths", "src"), ("--build-base", "build"), ("--install-base", "install")):
        assert args[args.index(option) + 1] == str(workspace / directory)
    assert "--merge-install" in args
    assert "--return-code-on-test-failure" in args
    if colcon_status:
        assert len(calls) == 1
    else:
        assert calls[1][2] == ["test-result", "--test-result-base", str(workspace / "build/spark_3dsg_pipeline"), "--verbose"]
        assert calls[2] == ["python3", str(repository), ["-m", "pytest", "-q", "tests"]]


def test_gpu_check_reuses_auxiliary_weights_between_runs(tmp_path, monkeypatch):
    model_dir = tmp_path / "persistent models"
    model_dir.mkdir()
    model = model_dir / "yoloe-26m-seg.pt"
    model.touch()
    downloads = []

    class FakeYOLOE:
        def __init__(self, filename):
            assert Path(filename) == model

        def set_classes(self, classes):
            assert classes == ["chair", "table"]
            assert Path.cwd() == model_dir
            weight = Path("mobileclip_blt.ts")
            if not weight.exists():
                downloads.append(weight)
                weight.write_text("fake text encoder")

    monkeypatch.setitem(sys.modules, "PIL", SimpleNamespace(__version__="11.3.0"))
    monkeypatch.setitem(sys.modules, "torchvision", SimpleNamespace(__version__="0.22.0"))
    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(__version__="8.4.130", YOLOE=FakeYOLOE))
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(
        __version__="2.7.0+cu128", version=SimpleNamespace(cuda="12.8"),
        backends=SimpleNamespace(cudnn=SimpleNamespace(version=lambda: 90701)),
        cuda=SimpleNamespace(is_available=lambda: True, get_device_name=lambda _: "fake GPU",
                             get_device_capability=lambda _: (12, 0)),
    ))
    script = (ROOT / "scripts/shell/gpu_smoke_test.sh").read_text()
    code = script.split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    monkeypatch.setattr(sys, "argv", ["-", str(model)])
    for _ in range(2):
        monkeypatch.chdir(tmp_path)
        exec(compile(code, "gpu_smoke_test.sh", "exec"), {})
    assert len(downloads) == 1
    assert (model_dir / "mobileclip_blt.ts").is_file()
