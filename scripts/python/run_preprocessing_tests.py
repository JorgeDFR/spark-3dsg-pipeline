#!/usr/bin/env python3
"""Orchestrate public-data preprocessing integration tests entirely through Docker."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, TextIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTAINER_ROOT = "/home/spark/spark-3dsg-pipeline"
CONTAINER_DATA = "/home/spark/data"
CONTAINER_NORMALIZED = "/home/spark/data/normalized/test-preprocess"
COMMAND_LOG: TextIO | None = None
VERBOSE = False


def run_command(invocation: list[str]) -> None:
    if COMMAND_LOG is None:
        subprocess.run(invocation, cwd=ROOT, check=True)
        return
    print("Command: " + " ".join(invocation), file=COMMAND_LOG, flush=True)
    if not VERBOSE:
        subprocess.run(
            invocation, cwd=ROOT, check=True,
            stdout=COMMAND_LOG, stderr=subprocess.STDOUT,
        )
        return
    with subprocess.Popen(
        invocation, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, errors="replace", bufsize=1,
    ) as process:
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="", flush=True)
            COMMAND_LOG.write(line)
            COMMAND_LOG.flush()
        status = process.wait()
    if status:
        raise subprocess.CalledProcessError(status, invocation)


def report_step(label: str, log: Path, action: Callable[[], None], verbose: bool) -> str | None:
    """Keep a full per-step transcript, including failures before bag creation."""
    global COMMAND_LOG, VERBOSE
    print(f"\n{'=' * 72}\nSTART {label}\n  Log: {log}", flush=True)
    started = time.monotonic()
    error_text = None
    previous = COMMAND_LOG, VERBOSE
    log.parent.mkdir(parents=True, exist_ok=True)
    try:
        with log.open("w", encoding="utf-8", buffering=1) as stream:
            COMMAND_LOG, VERBOSE = stream, verbose
            try:
                if verbose:
                    action()
                else:
                    with redirect_stdout(stream), redirect_stderr(stream):
                        action()
            except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
                print(str(error), file=stream)
                error_text = (
                    f"command exited with status {error.returncode}"
                    if isinstance(error, subprocess.CalledProcessError) else str(error)
                )
    finally:
        COMMAND_LOG, VERBOSE = previous
    status = "FAIL" if error_text else "PASS"
    print(f"{status:4}  {label}  ({time.monotonic() - started:.1f}s)", flush=True)
    if error_text:
        print(f"  {error_text}\n  Details: {log}", flush=True)
    print("-" * 72, flush=True)
    return error_text


@dataclass(frozen=True)
class Case:
    dataset: str
    input_path: str
    source: str
    preprocessor: str
    duration: int | None = None
    dependency: str | None = None
    experimental: bool = False
    required_topics: tuple[str, ...] = ()


def fixture_config(name: str, kind: str = "sources") -> str:
    return f"{CONTAINER_ROOT}/tests/fixtures/preprocessing/{kind}/{name}.yaml"


CASES = {
    "zed2_lake_zed_tracking": Case(
        "zed2_lake_h265",
        f"{CONTAINER_DATA}/raw/test-preprocess/ZED2_Lake_H265.svo",
        fixture_config("validation_zed2_lake"),
        "zed_tracking",
        duration=15,
    ),
    "zed2_lake_rtabmap": Case(
        "zed2_lake_h265",
        f"{CONTAINER_DATA}/raw/test-preprocess/ZED2_Lake_H265.svo",
        fixture_config("validation_zed2_lake"),
        "rtabmap_rgbd",
        required_topics=("/input/odometry",),
        duration=15,
    ),
    "uosm_zed2i_zed_tracking": Case(
        "uosm_zed2i_svo2",
        f"{CONTAINER_DATA}/raw/test-preprocess/UoSM_UF-01-N.svo2",
        "zed2i_svo",
        "zed_tracking",
        duration=15,
        required_topics=("/input/imu",),
    ),
    "d435i_recorded_odometry": Case(
        "d435i_run009",
        f"{CONTAINER_DATA}/raw/test-preprocess/d435i_run009_ros2",
        fixture_config("validation_d435i"),
        "recorded_odometry",
        required_topics=("/input/odometry",),
    ),
    "d435i_rtabmap": Case(
        "d435i_run009",
        f"{CONTAINER_DATA}/raw/test-preprocess/d435i_run009_ros2",
        fixture_config("validation_d435i"),
        "rtabmap_rgbd",
        required_topics=("/input/odometry",),
    ),
    "d435i_register_recorded_odometry": Case(
        "d435i_run009",
        f"{CONTAINER_DATA}/raw/test-preprocess/d435i_run009_ros2",
        fixture_config("validation_d435i_register"),
        "recorded_odometry",
        required_topics=("/input/odometry",),
    ),
    "d435i_register_rtabmap": Case(
        "d435i_run009",
        f"{CONTAINER_DATA}/raw/test-preprocess/d435i_run009_ros2",
        fixture_config("validation_d435i_register"),
        "rtabmap_rgbd",
        required_topics=("/input/odometry",),
    ),
    "d435i_openvins_mono": Case(
        "d435i_run009",
        f"{CONTAINER_DATA}/raw/test-preprocess/d435i_run009_ros2",
        fixture_config("validation_d435i"),
        fixture_config("openvins_mono", "preprocessing"),
        experimental=True,
        required_topics=("/input/imu", "/input/odometry"),
    ),
    "d435i_openvins_stereo": Case(
        "d435i_run009",
        f"{CONTAINER_DATA}/raw/test-preprocess/d435i_run009_ros2",
        fixture_config("validation_d435i"),
        fixture_config("openvins_stereo", "preprocessing"),
        experimental=True,
        required_topics=("/input/imu", "/input/odometry"),
    ),
    "d435i_passthrough": Case(
        "d435i_run009",
        f"{CONTAINER_NORMALIZED}/d435i_recorded_odometry",
        fixture_config("validation_d435i_normalized"),
        "passthrough",
        dependency="d435i_recorded_odometry",
    ),
    "tum_rtabmap": Case(
        "tum_fr1_xyz",
        f"{CONTAINER_DATA}/raw/test-preprocess/tum_fr1_xyz_ros2",
        fixture_config("validation_tum_fr1"),
        "rtabmap_rgbd",
        required_topics=("/input/odometry",),
    ),
}


def project_environment() -> dict[str, str]:
    values = dict(os.environ)
    path = ROOT / ".env"
    if path.is_file():
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values.setdefault(key.strip(), value)
    return values


def host_path(value: str, default: str) -> Path:
    path = Path(value or default).expanduser()
    return path if path.is_absolute() else (ROOT / path).resolve()


def compose_run(
    service: str,
    command: list[str],
    *,
    profile: str,
) -> None:
    invocation = ["docker", "compose", "--profile", profile, "run"]
    invocation.append("--rm")
    invocation.extend([service, *command])
    run_command(invocation)


def prepare(datasets: list[str]) -> None:
    command = [
        "python3",
        f"{CONTAINER_ROOT}/scripts/python/prepare_preprocessing_datasets.py",
    ]
    for dataset in datasets:
        command.extend(["--dataset", dataset])
    compose_run("preprocess", command, profile="preprocess")


def validate_output(case_name: str, case: Case) -> None:
    output = f"{CONTAINER_NORMALIZED}/{case_name}"
    compose_run(
        "preprocess",
        [
            "python3",
            f"{CONTAINER_ROOT}/scripts/python/validate_bag.py",
            "--bag",
            output,
            "--dataset",
            f"{output}/dataset.yaml",
            "--mapping",
            "closed_set",
        ],
        profile="preprocess",
    )
    validation = [
        "python3",
        f"{CONTAINER_ROOT}/scripts/python/validate_preprocessing_output.py",
        "--bag",
        output,
    ]
    for topic in case.required_topics:
        validation.extend(["--require-topic", topic])
    compose_run("preprocess", validation, profile="preprocess")


def run_case(name: str, case: Case) -> None:
    output = f"{CONTAINER_NORMALIZED}/{name}"
    command = [
        "python3",
        f"{CONTAINER_ROOT}/scripts/python/preprocess_bag.py",
        "--input",
        case.input_path,
        "--output",
        output,
        "--source",
        case.source,
        "--preprocessor",
        case.preprocessor,
        "--startup-timeout",
        "300" if case.duration is not None else "60",
    ]
    if case.duration is not None:
        command.extend(["--duration", str(case.duration)])
    compose_run("preprocess", command, profile="preprocess")
    validate_output(name, case)


def selected_cases(args: argparse.Namespace) -> list[str]:
    if args.case:
        unknown = sorted(set(args.case) - set(CASES))
        if unknown:
            raise ValueError(f"unknown case(s): {', '.join(unknown)}")
        names = list(dict.fromkeys(args.case))
    else:
        names = [
            name
            for name, case in CASES.items()
            if args.suite == "all" or not case.experimental
        ]
    expanded: list[str] = []
    for name in names:
        dependency = CASES[name].dependency
        if dependency and dependency not in expanded:
            expanded.append(dependency)
        if name not in expanded:
            expanded.append(name)
    return expanded


def remove_case_artifacts(output_root: Path, name: str) -> None:
    targets = [output_root / name]
    targets.extend(output_root.glob(f".{name}.tmp-*"))
    targets.extend(output_root.glob(f".{name}.logs-*"))
    for target in targets:
        if target.exists():
            shutil.rmtree(target)
            print(f"⌫ removed generated test artifact: {target}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("stable", "all"), default="all")
    parser.add_argument("--case", action="append", help="test case; repeatable")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--download-only", action="store_true")
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--verbose", action="store_true", help="also stream full command output")
    failure_mode = parser.add_mutually_exclusive_group()
    failure_mode.add_argument(
        "--keep-going", dest="keep_going", action="store_true", default=True,
        help="run independent cases after a failure (default)",
    )
    failure_mode.add_argument(
        "--fail-fast", dest="keep_going", action="store_false",
        help="stop after the first failed case",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="remove and regenerate only selected test outputs",
    )
    args = parser.parse_args()

    if args.list:
        for name, case in CASES.items():
            status = "experimental" if case.experimental else "stable"
            print(f"{name:32} {status:12} {case.dataset}")
        return 0

    try:
        names = selected_cases(args)
    except ValueError as error:
        parser.error(str(error))
    env = project_environment()
    data_root = host_path(env.get("DATA_DIR", ""), "./data")
    output_root = data_root / "normalized" / "test-preprocess"
    output_root.mkdir(parents=True, exist_ok=True)
    # Separate transcripts from case outputs so --force cannot remove the log
    # currently being written. Keep previous runs for comparing failures.
    log_root = output_root / "logs" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    print(f"Preprocessing tests: {len(names)} cases ({args.suite} suite)", flush=True)
    print(f"Console logs: {log_root}", flush=True)
    datasets = list(dict.fromkeys(CASES[name].dataset for name in names))
    preparation_errors: dict[str, str] = {}
    if not args.skip_download:
        for index, dataset in enumerate(datasets, 1):
            error = report_step(
                f"data {index}/{len(datasets)}: {dataset}",
                log_root / f"prepare-{dataset}.log",
                lambda dataset=dataset: prepare([dataset]), args.verbose,
            )
            if error:
                preparation_errors[dataset] = error
                if not args.keep_going:
                    break
    if args.download_only:
        print(f"Data preparation {'FAILED' if preparation_errors else 'PASSED'}. Logs: {log_root}")
        return 1 if preparation_errors else 0

    results: dict[str, str] = dict.fromkeys(names, "not run")
    for name in names:
        dataset = CASES[name].dataset
        if dataset in preparation_errors:
            results[name] = f"failed: dataset preparation: {preparation_errors[dataset]}"
    for index, name in enumerate(names, 1):
        label = f"case {index}/{len(names)}: {name}"
        if preparation_errors and not args.keep_going:
            break
        if CASES[name].dataset in preparation_errors:
            print(f"\nSKIP  {label} (dataset preparation failed)", flush=True)
            continue
        dependency = CASES[name].dependency
        if dependency and results.get(dependency) != "passed":
            results[name] = f"skipped: dependency {dependency} did not pass"
            print(f"\nSKIP  {label} ({results[name]})", flush=True)
            continue
        output = output_root / name
        cached = (output / "preprocessing_manifest.yaml").is_file() and not args.force

        def execute_case():
            if args.force:
                remove_case_artifacts(output_root, name)
            if cached:
                validate_output(name, CASES[name])
            elif output.exists():
                raise RuntimeError(
                    f"incomplete output exists; inspect it or rerun with --force: {output}"
                )
            else:
                run_case(name, CASES[name])

        error = report_step(
            label + (" [revalidate existing output]" if cached else " [preprocess]"),
            log_root / f"{name}.log", execute_case, args.verbose,
        )
        results[name] = f"failed: {error}" if error else "passed"
        if error and not args.keep_going:
            break

    summary = output_root / "summary.json"
    summary.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"\n{'=' * 72}\nVALIDATION RESULTS")
    for name, result in results.items():
        status = result.split(":", 1)[0].upper()
        print(f"  {status:8} {name}")
    passed = sum(result == "passed" for result in results.values())
    print(f"\n{passed}/{len(names)} passed\nSummary: {summary}\nLogs:    {log_root}", flush=True)
    return 0 if results and all(value == "passed" for value in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
