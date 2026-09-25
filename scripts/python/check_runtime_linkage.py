#!/usr/bin/env python3
"""Check installed ELF libraries/executables inside a runtime Docker image.

NVIDIA driver libraries are injected when the container starts with a GPU, so
build-time checks may explicitly allow those names. CUDA toolkit and SDK
libraries must still resolve in the image itself. This does not check dlopen
plugins; the end-to-end GPU/preprocessing tests remain necessary.
"""

import argparse
import os
from pathlib import Path
import re
import subprocess


DRIVER_LIBRARIES = frozenset({
    "libcuda.so.1",
    "libnvidia-ml.so.1",
    "libnvcuvid.so.1",
    "libnvidia-encode.so.1",
})


def check_linkage(root: Path, *, allow_driver_libraries: bool = False) -> list[str]:
    errors = []
    checked = set()
    if not root.is_dir():
        return [f"Missing install directory: {root}"]
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        resolved = path.resolve()
        if resolved in checked:
            continue
        with path.open("rb") as stream:
            header = stream.read(18)
        if len(header) < 18 or header[:4] != b"\x7fELF":
            continue
        byteorder = "little" if header[5] == 1 else "big"
        if int.from_bytes(header[16:18], byteorder) not in (2, 3):
            continue
        checked.add(resolved)
        result = subprocess.run(
            ["ldd", str(resolved)], capture_output=True, text=True,
            env={**os.environ, "LC_ALL": "C"}, check=False,
        )
        output = result.stdout + result.stderr
        if "not a dynamic executable" in output or "statically linked" in output:
            continue
        if result.returncode:
            errors.append(f"{path}: ldd failed: {output.strip()}")
            continue
        missing = set(re.findall(r"^\s*(\S+)\s+=>\s+not found\s*$", output, re.M))
        if allow_driver_libraries:
            missing -= DRIVER_LIBRARIES
        if missing:
            errors.append(f"{path}: missing {', '.join(sorted(missing))}")
    if not checked:
        errors.append(f"No ELF executables/libraries found in {root}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("install_dir", type=Path)
    parser.add_argument("--allow-driver-libraries", action="store_true")
    args = parser.parse_args()
    errors = check_linkage(
        args.install_dir, allow_driver_libraries=args.allow_driver_libraries,
    )
    if errors:
        parser.exit(1, "\n".join(errors) + "\n")
    print(f"Runtime linkage OK: {args.install_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
