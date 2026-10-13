"""Read external TUM poses and interpolate them without estimating a trajectory."""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import numpy as np


def seconds_to_ns(value: Any) -> int:
    try:
        seconds = Decimal(str(value))
        if not seconds.is_finite():
            raise ValueError("timestamp must be finite")
        return int((seconds * 1_000_000_000).to_integral_value())
    except (InvalidOperation, OverflowError) as error:
        raise ValueError(f"invalid timestamp: {value!r}") from error


def quaternion_product(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    a, b = left[:3], right[:3]
    return np.r_[left[3] * b + right[3] * a + np.cross(a, b),
                 left[3] * right[3] - np.dot(a, b)]


def quaternion_from_rotation(rotation: np.ndarray) -> np.ndarray:
    r = rotation
    matrix = np.array([
        [r[0, 0] - r[1, 1] - r[2, 2], r[1, 0] + r[0, 1], r[2, 0] + r[0, 2], r[2, 1] - r[1, 2]],
        [r[1, 0] + r[0, 1], r[1, 1] - r[0, 0] - r[2, 2], r[2, 1] + r[1, 2], r[0, 2] - r[2, 0]],
        [r[2, 0] + r[0, 2], r[2, 1] + r[1, 2], r[2, 2] - r[0, 0] - r[1, 1], r[1, 0] - r[0, 1]],
        [r[2, 1] - r[1, 2], r[0, 2] - r[2, 0], r[1, 0] - r[0, 1], np.trace(r)],
    ]) / 3
    _, vectors = np.linalg.eigh(matrix)
    quaternion = vectors[:, -1]
    return quaternion if quaternion[3] >= 0 else -quaternion


def slerp(left: np.ndarray, right: np.ndarray, fraction: float) -> np.ndarray:
    dot = float(np.dot(left, right))
    if dot < 0:
        right, dot = -right, -dot
    dot = min(1.0, dot)
    if dot > 0.9995:
        result = left + fraction * (right - left)
    else:
        angle = np.arccos(dot)
        result = (np.sin((1 - fraction) * angle) * left
                  + np.sin(fraction * angle) * right) / np.sin(angle)
    return result / np.linalg.norm(result)


@dataclass
class Trajectory:
    timestamps: list[int]
    positions: np.ndarray
    orientations: np.ndarray
    max_gap_ns: int
    missing: str

    def sample(self, timestamp: int) -> tuple[np.ndarray, np.ndarray] | None:
        index = bisect_left(self.timestamps, timestamp)
        if index < len(self.timestamps) and self.timestamps[index] == timestamp:
            return self.positions[index].copy(), self.orientations[index].copy()
        reason = "outside external trajectory coverage"
        if 0 < index < len(self.timestamps):
            gap = self.timestamps[index] - self.timestamps[index - 1]
            if gap <= self.max_gap_ns:
                fraction = (timestamp - self.timestamps[index - 1]) / gap
                position = ((1 - fraction) * self.positions[index - 1]
                            + fraction * self.positions[index])
                return position, slerp(
                    self.orientations[index - 1], self.orientations[index], fraction
                )
            reason = f"external trajectory interpolation gap {gap / 1e9:.6f}s exceeds limit"
        if self.missing == "drop":
            return None
        raise ValueError(f"{reason} at {timestamp / 1e9:.9f}s")


def load_trajectory(settings: dict[str, Any]) -> Trajectory:
    path = Path(settings["path"]).expanduser()
    offset = seconds_to_ns(settings.get("time_offset", 0.0))
    timestamps, positions, orientations = [], [], []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        fields = line.split("#", 1)[0].split()
        if not fields:
            continue
        try:
            if len(fields) != 8:
                raise ValueError("expected timestamp tx ty tz qx qy qz qw")
            timestamp = seconds_to_ns(fields[0]) + offset
            values = np.array([float(value) for value in fields[1:]])
            if timestamp < 0 or timestamp > (2**31 - 1) * 1_000_000_000 + 999_999_999:
                raise ValueError("timestamp is outside the ROS Time range")
            if not np.all(np.isfinite(values)):
                raise ValueError("pose values must be finite")
            norm = np.linalg.norm(values[3:])
            if not np.isfinite(norm) or norm < 1e-12:
                raise ValueError("quaternion must be nonzero and finite")
            if timestamps and timestamp <= timestamps[-1]:
                raise ValueError("timestamps must be strictly increasing")
        except ValueError as error:
            raise ValueError(f"{path}:{line_number}: {error}") from error
        timestamps.append(timestamp)
        positions.append(values[:3])
        orientations.append(values[3:] / norm)
    if len(timestamps) < 2:
        raise ValueError(f"external trajectory needs at least two poses: {path}")
    return Trajectory(
        timestamps, np.array(positions), np.array(orientations),
        seconds_to_ns(settings["max_gap"]), settings.get("missing", "error"),
    )
