from __future__ import annotations

import re
from dataclasses import dataclass

from .types import Environment


@dataclass(frozen=True)
class ParsedWeather:
    environment: Environment
    raw: str
    notes: list[str]


_WIND_RE = re.compile(r"\b(?P<dir>\d{3}|VRB)(?P<spd>\d{2,3})(?:G(?P<gust>\d{2,3}))?KT\b")
_TEMP_RE = re.compile(r"\b(?P<t>M?\d{2})/(?P<d>M?\d{2})\b")
_ALT_RE = re.compile(r"\bA(?P<a>\d{4})\b")
_QNH_RE = re.compile(r"\bQ(?P<q>\d{4})\b")


def _signed_temp(token: str) -> float:
    return -float(token[1:]) if token.startswith("M") else float(token)


def parse_metar(text: str, field_elevation_ft: float = 0.0) -> ParsedWeather:
    raw = " ".join(text.upper().strip().split())
    notes: list[str] = []
    wind_dir = None
    wind_speed = 0.0
    gust = None
    oat = 15.0
    qnh = 29.92

    m = _WIND_RE.search(raw)
    if m:
        wind_dir = None if m.group("dir") == "VRB" else float(m.group("dir"))
        wind_speed = float(m.group("spd"))
        gust = float(m.group("gust")) if m.group("gust") else None
    else:
        notes.append("Wind group not found; calm wind assumed.")

    m = _TEMP_RE.search(raw)
    if m:
        oat = _signed_temp(m.group("t"))
    else:
        notes.append("Temperature group not found; 15 C assumed.")

    m = _ALT_RE.search(raw)
    if m:
        qnh = float(m.group("a")) / 100.0
    else:
        q = _QNH_RE.search(raw)
        if q:
            hpa = float(q.group("q"))
            qnh = hpa * 0.0295299831
        else:
            notes.append("Altimeter/QNH group not found; 29.92 inHg assumed.")

    return ParsedWeather(
        Environment(
            field_elevation_ft=float(field_elevation_ft),
            oat_c=oat,
            qnh_inhg=qnh,
            wind_dir_deg=wind_dir,
            wind_speed_kt=wind_speed,
            wind_gust_kt=gust,
        ),
        raw,
        notes,
    )


def wind_components(wind_dir_deg: float | None, wind_speed_kt: float, runway_heading_deg: float) -> tuple[float, float]:
    if wind_dir_deg is None or wind_speed_kt <= 0:
        return 0.0, 0.0
    import math

    delta = math.radians(float(wind_dir_deg) - float(runway_heading_deg))
    headwind = float(wind_speed_kt) * math.cos(delta)
    crosswind = float(wind_speed_kt) * math.sin(delta)
    return headwind, crosswind
