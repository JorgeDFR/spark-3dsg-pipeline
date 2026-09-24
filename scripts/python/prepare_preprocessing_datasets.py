#!/usr/bin/env python3
"""Download and convert the small public preprocessing test datasets."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml


CHUNK_SIZE = 8 * 1024 * 1024
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
OPENVINS_COMMIT = "0bd027a997f3ca911b3df504d20b00b60f371b31"
OPENVINS_ESTIMATOR_URL = (
    "https://raw.githubusercontent.com/nathanshankar/open_vins/"
    f"{OPENVINS_COMMIT}/config/rpng_plane/estimator_config.yaml"
)


def download(url: str, destination: Path, expected_bytes: int | None) -> None:
    if destination.is_file():
        size = destination.stat().st_size
        if expected_bytes is None or size == expected_bytes:
            print(f"✓ download exists: {destination} ({size / 2**20:.1f} MiB)")
            return
        raise RuntimeError(
            f"existing download has {size} bytes, expected {expected_bytes}: "
            f"{destination}"
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(f".{destination.name}.part")
    offset = partial.stat().st_size if partial.exists() else 0
    headers = {"User-Agent": "spark-3dsg-pipeline-dataset-preparer/1"}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    request = urllib.request.Request(url, headers=headers)
    try:
        response = urllib.request.urlopen(request, timeout=60)
    except urllib.error.HTTPError as error:
        if offset and error.code == 416 and expected_bytes == offset:
            partial.replace(destination)
            return
        raise RuntimeError(f"download failed for {url}: {error}") from error

    append = offset > 0 and getattr(response, "status", None) == 206
    if not append:
        offset = 0
    mode = "ab" if append else "wb"
    copied = offset
    next_progress = copied + 256 * 1024 * 1024
    print(f"↓ {url}\n  -> {destination}")
    with response, partial.open(mode) as stream:
        while chunk := response.read(CHUNK_SIZE):
            stream.write(chunk)
            copied += len(chunk)
            if copied >= next_progress:
                total = expected_bytes or copied
                print(f"  {100.0 * copied / total:.0f}% ({copied / 2**20:.0f} MiB)")
                next_progress += 256 * 1024 * 1024
    if expected_bytes is not None and copied != expected_bytes:
        raise RuntimeError(
            f"download has {copied} bytes, expected {expected_bytes}: {partial}"
        )
    partial.replace(destination)
    print(f"✓ downloaded: {destination} ({copied / 2**20:.1f} MiB)")


def is_ros2_bag(path: Path) -> bool:
    return (
        path.is_dir()
        and (path / "metadata.yaml").is_file()
        and any(item.suffix in {".mcap", ".db3"} for item in path.iterdir())
    )


def migrate_legacy(sources: list[Path], destination: Path) -> None:
    existing = [source for source in sources if source.exists() and source != destination]
    if destination.exists():
        for source in existing:
            print(f"! legacy artifact remains beside staged path: {source}")
        return
    if len(existing) > 1:
        raise RuntimeError(
            "multiple legacy artifacts exist; reconcile them manually before "
            f"migration to {destination}: {', '.join(map(str, existing))}"
        )
    if not existing:
        return
    source = existing[0]
    destination.parent.mkdir(parents=True, exist_ok=True)
    source.rename(destination)
    print(f"↻ migrated test artifact: {source} -> {destination}")


def prune_legacy_prepared_directories(data_dir: Path) -> None:
    for relative in (
        "prepared/validation/calibration",
        "prepared/validation",
        "prepared",
    ):
        try:
            (data_dir / relative).rmdir()
        except OSError:
            pass


def convert_ros1(
    source: Path, destination: Path, include_topics: list[str] | None = None
) -> None:
    if is_ros2_bag(destination):
        print(f"✓ converted bag exists: {destination}")
        return
    if destination.exists():
        raise RuntimeError(f"refusing to replace incomplete conversion: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(destination.parent).free
    if free < 2 * source.stat().st_size:
        raise RuntimeError(
            f"not enough free space to convert {source.name}: need approximately "
            f"{2 * source.stat().st_size / 2**30:.1f} GiB"
        )
    temporary = destination.with_name(f".{destination.name}.converting")
    if temporary.exists():
        raise RuntimeError(f"remove incomplete conversion before retrying: {temporary}")
    print(f"↻ converting ROS 1 bag: {source} -> {destination}")
    command = ["rosbags-convert", "--src", str(source), "--dst", str(temporary)]
    if include_topics:
        command.extend(["--include-topic", *include_topics])
    subprocess.run(command, check=True)
    if not is_ros2_bag(temporary):
        raise RuntimeError(f"conversion did not create a ROS 2 bag: {temporary}")
    temporary.rename(destination)
    print(f"✓ converted: {destination}")


def write_openvins_calibration(data_dir: Path) -> None:
    destination = data_dir / "raw/test-preprocess/calibration/openvins"
    destination.mkdir(parents=True, exist_ok=True)
    download(
        OPENVINS_ESTIMATOR_URL,
        destination / "estimator_config.yaml",
        5910,
    )
    imu = """%YAML:1.0
imu0:
  T_i_b:
    - [1.0, 0.0, 0.0, 0.0]
    - [0.0, 1.0, 0.0, 0.0]
    - [0.0, 0.0, 1.0, 0.0]
    - [0.0, 0.0, 0.0, 1.0]
  accelerometer_noise_density: 0.002
  accelerometer_random_walk: 0.0003
  gyroscope_noise_density: 0.00014
  gyroscope_random_walk: 0.00002
  rostopic: /mavros/imu/data
  time_offset: 0.0
  update_rate: 200.0
  model: calibrated
  Tw: [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
  R_IMUtoGYRO: [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
  Ta: [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
  R_IMUtoACC: [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
  Tg: [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
"""
    imucam = """%YAML:1.0
cam0:
  T_cam_imu:
    - [0.00210611851338, -0.99997531715, 0.00670293628313, 0.0153589401799]
    - [-0.0104500478822, -0.00672459373869, -0.999922785188, -0.115577447119]
    - [0.999943178768, 0.00203590988481, -0.0104639527367, -0.0534651855625]
    - [0.0, 0.0, 0.0, 1.0]
  cam_overlaps: [1]
  camera_model: pinhole
  distortion_coeffs: [0.0035534305077957393, -0.005453237129435213, 0.00010675207504647932, 0.0009528909894796479]
  distortion_model: radtan
  intrinsics: [380.23038427459284, 381.1265029215647, 320.6907544876677, 242.3473400097656]
  resolution: [640, 480]
  rostopic: /camera/infra1/image_rect_raw
  timeshift_cam_imu: 0.0
cam1:
  T_cam_imu:
    - [0.0015917856736, -0.99997648483, 0.00667053247829, -0.034619352623]
    - [-0.0113983572986, -0.00668825094773, -0.999912668561, -0.115624343094]
    - [0.999933769641, 0.00151561354756, -0.0114087355258, -0.0536899168878]
    - [0.0, 0.0, 0.0, 1.0]
  cam_overlaps: [0]
  camera_model: pinhole
  distortion_coeffs: [0.002771483511096517, -0.0031009478406697844, 0.0002884028295937648, 0.0006861519410837503]
  distortion_model: radtan
  intrinsics: [381.11061604724665, 381.92307304912975, 319.1547350093929, 241.69327971162363]
  resolution: [640, 480]
  rostopic: /camera/infra2/image_rect_raw
  timeshift_cam_imu: 0.0
"""
    (destination / "kalibr_imu_chain.yaml").write_text(imu, encoding="utf-8")
    (destination / "kalibr_imucam_chain.yaml").write_text(
        imucam, encoding="utf-8"
    )
    print(f"✓ OpenVINS test calibration: {destination}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("/home/spark/data"))
    parser.add_argument(
        "--manifest",
        type=Path,
        default=REPOSITORY_ROOT / "tests/fixtures/preprocessing/datasets.yaml",
    )
    parser.add_argument(
        "--dataset", action="append", dest="datasets", help="dataset name; repeatable"
    )
    parser.add_argument("--list", action="store_true", help="list datasets and exit")
    parser.add_argument("--no-convert", action="store_true")
    args = parser.parse_args()

    root = yaml.safe_load(args.manifest.read_text(encoding="utf-8"))
    available = root["datasets"]
    if args.list:
        for name, entry in available.items():
            print(f"{name:20} {entry['bytes'] / 2**20:8.1f} MiB  {entry['description']}")
        return 0
    selected = args.datasets or list(available)
    unknown = sorted(set(selected) - set(available))
    if unknown:
        parser.error(f"unknown dataset(s): {', '.join(unknown)}")

    try:
        for name in selected:
            entry = available[name]
            source = args.data_dir / entry["relative_path"]
            migrate_legacy(
                [args.data_dir / path for path in entry.get("legacy_relative_paths", [])],
                source,
            )
            download(entry["url"], source, entry.get("bytes"))
            if entry["format"] == "rosbag1" and not args.no_convert:
                destination = args.data_dir / entry["converted_path"]
                migrate_legacy(
                    [
                        args.data_dir / path
                        for path in entry.get("legacy_converted_paths", [])
                    ],
                    destination,
                )
                convert_ros1(
                    source,
                    destination,
                    entry.get("include_topics"),
                )
        if "d435i_run009" in selected:
            migrate_legacy(
                [
                    args.data_dir / "raw/validation/calibration/openvins",
                    args.data_dir / "raw/qualification/calibration/openvins",
                    args.data_dir / "prepared/qualification/calibration/openvins",
                    args.data_dir / "prepared/validation/calibration/openvins",
                    args.data_dir / "normalized/calibration/openvins",
                ],
                args.data_dir / "raw/test-preprocess/calibration/openvins",
            )
            write_openvins_calibration(args.data_dir)
        prune_legacy_prepared_directories(args.data_dir)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"dataset preparation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
