#!/usr/bin/env python3
"""Extract reproducible F-14 motion data from Tacview ACMI archives.

The parser intentionally treats cockpit-engine data conservatively. Tacview's
DCS exporter supplies throttle-handle ratio for the attached recordings, but
not EIG RPM or per-engine fuel flow. Those values are therefore inventoried
and never inferred from throttle position or the non-standard FuelWeight field.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, field
import io
import json
import math
from pathlib import Path
import statistics
import zipfile


MS_TO_KT = 1.9438444924406
M_TO_FT = 3.2808398950131


@dataclass
class ObjectState:
    properties: dict[str, str] = field(default_factory=dict)
    transform: list[float | None] = field(default_factory=lambda: [None] * 9)


@dataclass(frozen=True)
class Frame:
    time_s: float
    u_m: float | None
    v_m: float | None
    altitude_m: float | None
    pitch_deg: float | None
    ias_ms: float | None
    agl_m: float | None
    throttle: float | None
    throttle2: float | None
    flaps: float | None
    gear: float | None
    fuel_weight: float | None
    fuel_flow_weight: float | None
    fuel_flow_weight2: float | None
    engine_rpm: float | None
    engine_rpm2: float | None


def _number(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _archive_members(path: Path):
    """Yield ``(display_name, text)`` from a ZIP, nested ZIP ACMI, or text ACMI."""
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as outer:
            for member in outer.infolist():
                if member.is_dir():
                    continue
                raw = outer.read(member)
                member_path = Path(member.filename)
                if zipfile.is_zipfile(io.BytesIO(raw)):
                    with zipfile.ZipFile(io.BytesIO(raw)) as inner:
                        for nested in inner.infolist():
                            if nested.is_dir():
                                continue
                            yield (
                                f"{member_path.name}::{Path(nested.filename).name}",
                                inner.read(nested).decode("utf-8-sig", errors="replace"),
                            )
                elif member_path.suffix.lower() == ".acmi":
                    yield member_path.name, raw.decode("utf-8-sig", errors="replace")
    else:
        yield path.name, path.read_text(encoding="utf-8-sig", errors="replace")


def _update_transform(current: list[float | None], raw: str) -> list[float | None]:
    values = raw.split("|")
    updated = list(current)
    # ACMI uses compact transform syntaxes. Five fields means lon/lat/alt/U/V,
    # not lon/lat/alt/roll/pitch. Six fields adds attitude, while the full
    # nine-field form includes both attitude and native U/V coordinates.
    if len(values) == 3:
        indexes = (0, 1, 2)
    elif len(values) == 5:
        indexes = (0, 1, 2, 6, 7)
    elif len(values) == 6:
        indexes = (0, 1, 2, 3, 4, 5)
    elif len(values) == 9:
        indexes = tuple(range(9))
    else:
        indexes = tuple(range(min(len(values), len(updated))))
    for index, value in zip(indexes, values):
        if value != "":
            updated[index] = _number(value)
    return updated


def parse_acmi(text: str) -> tuple[dict[str, str], dict[str, list[Frame]], set[str]]:
    metadata: dict[str, str] = {}
    states: dict[str, ObjectState] = {}
    frames_by_object: dict[str, list[Frame]] = {}
    seen_properties: set[str] = set()
    time_s = 0.0

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            time_s = float(line[1:])
            continue
        if line.startswith("-"):
            states.pop(line[1:], None)
            continue
        if "," not in line:
            continue
        object_id, property_text = line.split(",", 1)
        state = states.setdefault(object_id, ObjectState())
        changed = False
        for token in property_text.split(","):
            if "=" not in token:
                continue
            key, value = token.split("=", 1)
            seen_properties.add(key)
            if object_id == "0":
                metadata[key] = value
                continue
            if key == "T":
                state.transform = _update_transform(state.transform, value)
            else:
                state.properties[key] = value
            changed = True

        name = state.properties.get("Name", "")
        object_type = state.properties.get("Type", "")
        if not changed or "FixedWing" not in object_type or not name.upper().startswith("F-14B"):
            continue

        t = state.transform + [None] * max(0, 9 - len(state.transform))
        p = state.properties
        frames_by_object.setdefault(object_id, []).append(
            Frame(
                time_s=time_s,
                u_m=t[6],
                v_m=t[7],
                altitude_m=t[2],
                pitch_deg=t[4],
                ias_ms=_number(p.get("IAS")),
                agl_m=_number(p.get("AGL")),
                throttle=_number(p.get("Throttle")),
                throttle2=_number(p.get("Throttle2")),
                flaps=_number(p.get("Flaps")),
                gear=_number(p.get("LandingGear")),
                fuel_weight=_number(p.get("FuelWeight")),
                fuel_flow_weight=_number(p.get("FuelFlowWeight")),
                fuel_flow_weight2=_number(p.get("FuelFlowWeight2")),
                engine_rpm=_number(p.get("EngineRPM")),
                engine_rpm2=_number(p.get("EngineRPM2")),
            )
        )
    return metadata, frames_by_object, seen_properties


def _distance_m(a: Frame, b: Frame) -> float:
    if None not in (a.u_m, a.v_m, b.u_m, b.v_m):
        return math.hypot(float(b.u_m) - float(a.u_m), float(b.v_m) - float(a.v_m))
    return 0.0


def _takeoff_summary(frames: list[Frame]) -> dict[str, float | str | None] | None:
    usable = [f for f in frames if f.ias_ms is not None and f.agl_m is not None]
    if len(usable) < 20 or max(f.ias_ms or 0.0 for f in usable) < 55.0:
        return None

    # Find the first sustained airborne point following a takeoff acceleration.
    liftoff_index = None
    for index, frame in enumerate(usable):
        if (frame.ias_ms or 0.0) < 35.0 or (frame.agl_m or 0.0) < 4.5:
            continue
        future = usable[index : index + 12]
        if len(future) >= 6 and all((f.agl_m or 0.0) > 3.5 for f in future):
            if future[-1].agl_m is not None and future[-1].agl_m > (frame.agl_m or 0.0) + 1.0:
                liftoff_index = index
                break
    if liftoff_index is None:
        return None

    liftoff = usable[liftoff_index]
    search_start = max(0, liftoff_index - 1800)
    start_index = None
    for index in range(liftoff_index - 1, search_start - 1, -1):
        frame = usable[index]
        if liftoff.time_s - frame.time_s > 180.0:
            break
        if (frame.ias_ms or 0.0) <= 3.0 and (frame.agl_m or 999.0) < 3.0:
            start_index = index
            break
    if start_index is None:
        return None
    start = usable[start_index]

    roll = usable[start_index : liftoff_index + 1]
    cumulative = 0.0
    distances = [0.0]
    for previous, current in zip(roll, roll[1:]):
        step = _distance_m(previous, current)
        if step < 100.0:
            cumulative += step
        distances.append(cumulative)

    baseline_pitch_values = [
        f.pitch_deg for f in roll[: min(25, len(roll))] if f.pitch_deg is not None
    ]
    baseline_pitch = statistics.median(baseline_pitch_values) if baseline_pitch_values else 0.0
    rotation_offset = None
    for index, frame in enumerate(roll):
        if (frame.ias_ms or 0.0) < 35.0 or frame.pitch_deg is None:
            continue
        if frame.pitch_deg >= baseline_pitch + 2.0:
            future = roll[index : index + 6]
            if len(future) >= 3 and sum(
                f.pitch_deg is not None and f.pitch_deg >= baseline_pitch + 1.5
                for f in future
            ) >= 3:
                rotation_offset = index
                break

    rotation = roll[rotation_offset] if rotation_offset is not None else None
    pre_liftoff = roll[max(0, len(roll) - 100) :]
    flaps = [f.flaps for f in roll if f.flaps is not None]
    throttles = [f.throttle for f in pre_liftoff if f.throttle is not None]
    return {
        "brake_release_time_s": round(start.time_s, 2),
        "rotation_time_s": round(rotation.time_s, 2) if rotation else None,
        "liftoff_time_s": round(liftoff.time_s, 2),
        "roll_time_s": round(liftoff.time_s - start.time_s, 2),
        "rotation_ias_kt": round((rotation.ias_ms or 0.0) * MS_TO_KT, 1) if rotation else None,
        "liftoff_ias_kt": round((liftoff.ias_ms or 0.0) * MS_TO_KT, 1),
        "rotation_distance_ft": round(distances[rotation_offset] * M_TO_FT) if rotation_offset is not None else None,
        "liftoff_distance_ft": round(distances[-1] * M_TO_FT),
        "liftoff_agl_ft": round((liftoff.agl_m or 0.0) * M_TO_FT, 1),
        "max_flap_ratio_before_liftoff": round(max(flaps), 3) if flaps else None,
        "median_throttle_last_roll": round(statistics.median(throttles), 3) if throttles else None,
        "fuel_weight_start_raw": start.fuel_weight,
        "fuel_weight_liftoff_raw": liftoff.fuel_weight,
    }


def analyze(path: Path, name_filter: str | None = None) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    paths = sorted(path.iterdir()) if path.is_dir() else [path]
    for source_path in paths:
        if source_path.is_dir() or (name_filter and name_filter not in source_path.name):
            continue
        for display_name, text in _archive_members(source_path):
            if name_filter and name_filter not in display_name and name_filter not in source_path.name:
                continue
            metadata, objects, properties = parse_acmi(text)
            for object_id, frames in objects.items():
                takeoff = _takeoff_summary(frames)
                if takeoff is None:
                    continue
                results.append(
                    {
                        "recording": display_name,
                        "object_id": object_id,
                        "title": metadata.get("Title"),
                        "recording_time": metadata.get("RecordingTime"),
                        "dcs_version": metadata.get("DataSource"),
                        "qnh_hpa": _number(metadata.get("QNH")),
                        "has_ff_telemetry": "FuelFlowWeight" in properties or "FuelFlowWeight2" in properties,
                        "has_rpm_telemetry": "EngineRPM" in properties or "EngineRPM2" in properties,
                        "has_fuel_weight": "FuelWeight" in properties,
                        **takeoff,
                    }
                )
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--match", help="Only analyze recording names containing this text")
    parser.add_argument("--csv", type=Path)
    args = parser.parse_args()
    results = analyze(args.archive, args.match)
    print(json.dumps(results, indent=2))
    if args.csv and results:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with args.csv.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(results[0]))
            writer.writeheader()
            writer.writerows(results)


if __name__ == "__main__":
    main()
