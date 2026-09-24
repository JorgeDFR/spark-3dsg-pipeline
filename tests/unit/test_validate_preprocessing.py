from pathlib import Path
import run_preprocessing_tests


def test_prepare_uses_preprocess_image_without_implicit_build(monkeypatch):
    calls = []

    def fake_run(command, cwd, check):
        calls.append((command, cwd, check))

    monkeypatch.setattr(run_preprocessing_tests.subprocess, "run", fake_run)

    run_preprocessing_tests.prepare(["tum_fr1_xyz"])

    command, cwd, check = calls[0]
    assert command[:4] == ["docker", "compose", "--profile", "preprocess"]
    assert "preprocess" in command
    assert "--build" not in command
    service_index = command.index("--rm") + 1
    assert command[service_index] == "preprocess"
    assert command[service_index + 1 : service_index + 3] == [
        "python3",
        "/home/spark/spark-3dsg-pipeline/scripts/python/prepare_preprocessing_datasets.py",
    ]
    assert cwd == run_preprocessing_tests.ROOT
    assert check is True


def test_validation_inputs_follow_staged_data_layout():
    for case in run_preprocessing_tests.CASES.values():
        relative = case.input_path.removeprefix("/home/spark/data/")
        assert relative.split("/", 1)[0] in {"raw", "normalized"}
        assert "/preprocessing/" not in case.input_path


def test_compose_run_does_not_use_unsupported_gpus_flag(monkeypatch):
    calls = []

    def fake_run(command, cwd, check):
        calls.append(command)

    monkeypatch.setattr(run_preprocessing_tests.subprocess, "run", fake_run)

    run_preprocessing_tests.compose_run(
        "preprocess", ["python3", "tool.py"], profile="preprocess"
    )

    assert calls[0][calls[0].index("--rm") + 1] == "preprocess"
    assert "--gpus" not in calls[0]


def test_force_cleanup_is_scoped_to_one_validation_case(tmp_path):
    output = tmp_path / "case"
    temporary = tmp_path / ".case.tmp-123"
    logs = tmp_path / ".case.logs-456"
    unrelated = tmp_path / "other"
    for path in (output, temporary, logs, unrelated):
        path.mkdir()

    run_preprocessing_tests.remove_case_artifacts(tmp_path, "case")

    assert not output.exists()
    assert not temporary.exists()
    assert not logs.exists()
    assert unrelated.is_dir()


def test_full_suite_covers_every_profile_and_both_registration_paths():
    from argparse import Namespace
    from preprocessing_config import config_directory, resolve_config
    from spark_3dsg_preprocessing.config import load_source

    names = run_preprocessing_tests.selected_cases(Namespace(case=None, suite="all"))
    cases = [run_preprocessing_tests.CASES[name] for name in names]
    profiles = {path.stem for path in config_directory("preprocessing").glob("*.yaml")}
    assert {Path(case.preprocessor).stem for case in cases} == profiles
    registering = {
        Path(case.preprocessor).stem for case in cases
        if load_source(resolve_config(case.source.replace(run_preprocessing_tests.CONTAINER_ROOT, str(run_preprocessing_tests.ROOT)), "sources"))["depth"]["mode"] == "register"
    }
    assert {"recorded_odometry", "rtabmap_rgbd"} <= registering
    assert names.index("d435i_recorded_odometry") < names.index("d435i_passthrough")


def test_default_runs_all_cases_despite_case_failure(monkeypatch, tmp_path):
    import json
    import sys

    monkeypatch.setattr(sys, "argv", ["run_preprocessing_tests.py", "--skip-download"])
    monkeypatch.setattr(run_preprocessing_tests, "project_environment", lambda: {"DATA_DIR": str(tmp_path)})
    calls = []
    def run(name, case):
        calls.append(name)
        if name == "zed2_lake_zed_tracking":
            raise RuntimeError("SDK unavailable")
    monkeypatch.setattr(run_preprocessing_tests, "run_case", run)
    assert run_preprocessing_tests.main() == 1
    assert set(calls) == set(run_preprocessing_tests.CASES)
    results = json.loads((tmp_path / "normalized/test-preprocess/summary.json").read_text())
    assert results["d435i_openvins_stereo"] == "passed"
    assert results["zed2_lake_zed_tracking"].startswith("failed:")


def test_download_failure_is_reported_without_blocking_other_datasets(monkeypatch, tmp_path):
    import json
    import subprocess
    import sys

    monkeypatch.setattr(sys, "argv", ["run_preprocessing_tests.py"])
    monkeypatch.setattr(run_preprocessing_tests, "project_environment", lambda: {"DATA_DIR": str(tmp_path)})
    def prepare(datasets):
        if datasets == ["zed2_lake_h265"]:
            raise subprocess.CalledProcessError(1, "download")
    monkeypatch.setattr(run_preprocessing_tests, "prepare", prepare)
    calls = []
    monkeypatch.setattr(run_preprocessing_tests, "run_case", lambda name, case: calls.append(name))
    assert run_preprocessing_tests.main() == 1
    assert "zed2_lake_rtabmap" not in calls
    assert "d435i_openvins_mono" in calls
    results = json.loads((tmp_path / "normalized/test-preprocess/summary.json").read_text())
    assert "dataset preparation" in results["zed2_lake_rtabmap"]


def test_quiet_step_keeps_child_stdout_and_stderr_in_log(tmp_path, capsys):
    import sys

    log = tmp_path / "case.log"
    error = run_preprocessing_tests.report_step(
        "case 1/2: example", log,
        lambda: run_preprocessing_tests.run_command([
            sys.executable, "-c",
            "import sys; print('child output'); print('loader failure', file=sys.stderr); sys.exit(3)",
        ]), False,
    )
    terminal = capsys.readouterr().out
    assert "START case 1/2: example" in terminal
    assert "FAIL  case 1/2: example" in terminal
    assert "loader failure" not in terminal
    assert "child output" not in terminal
    assert "loader failure" in log.read_text()
    assert "child output" in log.read_text()
    assert error == "command exited with status 3"
    assert run_preprocessing_tests.COMMAND_LOG is None


def test_verbose_step_tees_child_output_and_reports_success(tmp_path, capsys):
    import sys

    log = tmp_path / "case.log"
    error = run_preprocessing_tests.report_step(
        "case 1/1: example", log,
        lambda: run_preprocessing_tests.run_command([sys.executable, "-c", "print('child output')"]),
        True,
    )
    terminal = capsys.readouterr().out
    assert "child output" in terminal
    assert "PASS  case 1/1: example" in terminal
    assert "child output" in log.read_text()
    assert error is None
