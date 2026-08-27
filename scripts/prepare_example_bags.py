#!/usr/bin/env python3
"""Prepare known public example bags under canonical data-directory names."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


SPOT_CANONICAL = "spot"
SPOT_ARCHIVES = {
    "adt4_spot_example_bag.zip",
    "2025-09-04-heracles-eval-3-bag.zip",
}
SPOT_DIRECTORIES = {"2025-09-04-heracles-eval-3-bag"}

UHUMANS2_CANONICAL = "uhumans2"
UHUMANS2_ROS1_FILES = {
    "uhumans2_office_s1_00h_v2.bag",
    "uhumans2_office_s1_00h.bag",
}
UHUMANS2_ARCHIVES = {
    "uhumans2_office_s1_00h_v2.zip",
    "uhumans2_office_s1_00h_v2.bag.zip",
    "uhumans2_office_s1_00h.zip",
}
UHUMANS2_DIRECTORIES = {
    "uhumans2_office_s1_00h_v2",
    "uhumans2_office_s1_00h_v2_ros2",
    "uhumans2_office_s1_00h_ros2",
}

STORAGE_SUFFIXES = {".db3", ".mcap"}
COPY_BUFFER_SIZE = 16 * 1024 * 1024
PROGRESS_INTERVAL = 1024 * 1024 * 1024


def folded(value: str) -> str:
    return value.casefold()


def is_ros2_bag(path: Path) -> bool:
    if not path.is_dir() or not (path / "metadata.yaml").is_file():
        return False
    return any(
        child.is_file() and child.suffix.casefold() in STORAGE_SUFFIXES
        for child in path.iterdir()
    )


def require_free_space(root: Path, required: int) -> None:
    free = shutil.disk_usage(root).free
    if free < required:
        raise RuntimeError(
            f"insufficient free space under {root}: need {required / 2**30:.1f} GiB, "
            f"have {free / 2**30:.1f} GiB"
        )


def canonical_ready(path: Path) -> bool:
    if is_ros2_bag(path):
        print(f"✓ {path.name}: already prepared at {path}")
        return True
    if os.path.lexists(path):
        raise RuntimeError(f"refusing to replace non-bag canonical path: {path}")
    return False


def link_canonical(source: Path, canonical: Path) -> None:
    relative = os.path.relpath(source, canonical.parent)
    canonical.symlink_to(relative, target_is_directory=True)
    print(f"✓ {canonical.name}: linked {canonical} -> {relative}")


def known_child(root: Path, names: set[str]) -> Path | None:
    wanted = {folded(name) for name in names}
    for child in sorted(root.iterdir()):
        if child.name.casefold() in wanted:
            return child
    return None


def ros2_members(
    archive: zipfile.ZipFile, known_directories: set[str], archive_is_known: bool
) -> list[zipfile.ZipInfo] | None:
    known = {folded(name) for name in known_directories}
    infos = [info for info in archive.infolist() if not info.is_dir()]
    for metadata in infos:
        path = PurePosixPath(metadata.filename)
        if path.name != "metadata.yaml":
            continue
        parent = path.parent
        if not archive_is_known and parent.name.casefold() not in known:
            continue
        storage = [
            info
            for info in infos
            if PurePosixPath(info.filename).parent == parent
            and PurePosixPath(info.filename).suffix.casefold() in STORAGE_SUFFIXES
        ]
        if storage:
            return [metadata, *storage]
    return None


def ros1_member(
    archive: zipfile.ZipFile, known_files: set[str], archive_is_known: bool
) -> zipfile.ZipInfo | None:
    wanted = {folded(name) for name in known_files}
    candidates = [
        info
        for info in archive.infolist()
        if not info.is_dir() and PurePosixPath(info.filename).suffix.casefold() == ".bag"
    ]
    for info in candidates:
        if PurePosixPath(info.filename).name.casefold() in wanted:
            return info
    if archive_is_known and len(candidates) == 1:
        return candidates[0]
    return None


def copy_member(
    archive: zipfile.ZipFile, member: zipfile.ZipInfo, destination: Path
) -> None:
    print(
        f"  extracting {PurePosixPath(member.filename).name} "
        f"({member.file_size / 2**30:.1f} GiB)"
    )
    copied = 0
    next_progress = PROGRESS_INTERVAL
    with archive.open(member) as source, destination.open("wb") as output:
        while chunk := source.read(COPY_BUFFER_SIZE):
            output.write(chunk)
            copied += len(chunk)
            if copied >= next_progress and member.file_size:
                print(f"    {100.0 * copied / member.file_size:.0f}%")
                next_progress += PROGRESS_INTERVAL


def extract_ros2_archive(
    archive_path: Path, members: list[zipfile.ZipInfo], canonical: Path
) -> None:
    required = sum(member.file_size for member in members)
    require_free_space(canonical.parent, required)
    with tempfile.TemporaryDirectory(
        prefix=f".{canonical.name}.extracting-", dir=canonical.parent
    ) as temporary:
        bag = Path(temporary) / "bag"
        bag.mkdir()
        with zipfile.ZipFile(archive_path) as archive:
            for member in members:
                copy_member(
                    archive, member, bag / PurePosixPath(member.filename).name
                )
        if not is_ros2_bag(bag):
            raise RuntimeError(f"archive did not produce a valid ROS 2 bag: {archive_path}")
        bag.rename(canonical)
    print(f"✓ {canonical.name}: extracted to {canonical}")


def convert_ros1(source: Path, canonical: Path, converter: str) -> None:
    require_free_space(canonical.parent, source.stat().st_size)
    with tempfile.TemporaryDirectory(
        prefix=f".{canonical.name}.converting-", dir=canonical.parent
    ) as temporary:
        destination = Path(temporary) / "converted"
        print(f"  converting ROS 1 bag {source.name} to ROS 2")
        subprocess.run(
            [converter, "--src", str(source), "--dst", str(destination)], check=True
        )
        if not is_ros2_bag(destination):
            raise RuntimeError(f"conversion did not produce a valid ROS 2 bag: {source}")
        destination.rename(canonical)
    print(f"✓ {canonical.name}: converted to {canonical}")


def convert_ros1_archive(
    archive_path: Path,
    member: zipfile.ZipInfo,
    canonical: Path,
    converter: str,
) -> None:
    require_free_space(canonical.parent, 2 * member.file_size)
    with tempfile.TemporaryDirectory(
        prefix=f".{canonical.name}.source-", dir=canonical.parent
    ) as temporary:
        source = Path(temporary) / PurePosixPath(member.filename).name
        with zipfile.ZipFile(archive_path) as archive:
            copy_member(archive, member, source)
        convert_ros1(source, canonical, converter)


def zip_candidates(root: Path) -> list[Path]:
    return sorted(
        child
        for child in root.iterdir()
        if child.is_file() and child.suffix.casefold() == ".zip"
    )


def prepare_spot(root: Path) -> bool:
    canonical = root / SPOT_CANONICAL
    if canonical_ready(canonical):
        return True

    extracted = known_child(root, SPOT_DIRECTORIES)
    if extracted and is_ros2_bag(extracted):
        link_canonical(extracted, canonical)
        return True

    known_archives = {folded(name) for name in SPOT_ARCHIVES}
    for candidate in zip_candidates(root):
        with zipfile.ZipFile(candidate) as archive:
            members = ros2_members(
                archive,
                SPOT_DIRECTORIES,
                candidate.name.casefold() in known_archives,
            )
        if members:
            extract_ros2_archive(candidate, members, canonical)
            return True

    print("! spot: no known archive or extracted bag found")
    return False


def prepare_uhumans2(root: Path, converter: str) -> bool:
    canonical = root / UHUMANS2_CANONICAL
    if canonical_ready(canonical):
        return True

    extracted = known_child(root, UHUMANS2_DIRECTORIES)
    if extracted:
        if is_ros2_bag(extracted):
            link_canonical(extracted, canonical)
            return True
        source = known_child(extracted, UHUMANS2_ROS1_FILES)
        if source and source.is_file():
            convert_ros1(source, canonical, converter)
            return True

    source = known_child(root, UHUMANS2_ROS1_FILES)
    if source and source.is_file():
        convert_ros1(source, canonical, converter)
        return True

    known_archives = {folded(name) for name in UHUMANS2_ARCHIVES}
    for candidate in zip_candidates(root):
        archive_is_known = candidate.name.casefold() in known_archives
        with zipfile.ZipFile(candidate) as archive:
            members = ros2_members(
                archive, UHUMANS2_DIRECTORIES, archive_is_known
            )
            source_member = ros1_member(
                archive, UHUMANS2_ROS1_FILES, archive_is_known
            )
        if members:
            extract_ros2_archive(candidate, members, canonical)
            return True
        if source_member:
            convert_ros1_archive(candidate, source_member, canonical, converter)
            return True

    print("! uhumans2: no known archive, ROS 1 bag, or extracted bag found")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir", type=Path, default=Path.home() / "data", help="mounted data root"
    )
    parser.add_argument(
        "--dataset", choices=("all", "spot", "uhumans2"), default="all"
    )
    parser.add_argument("--converter", default="rosbags-convert", help=argparse.SUPPRESS)
    args = parser.parse_args()

    root = args.data_dir.resolve()
    if not root.is_dir():
        print(f"data directory does not exist: {root}", file=sys.stderr)
        return 2

    try:
        results: list[bool] = []
        if args.dataset in {"all", "spot"}:
            results.append(prepare_spot(root))
        if args.dataset in {"all", "uhumans2"}:
            results.append(prepare_uhumans2(root, args.converter))
    except (OSError, RuntimeError, subprocess.CalledProcessError, zipfile.BadZipFile) as error:
        print(f"data preparation failed: {error}", file=sys.stderr)
        return 1

    return 0 if any(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
