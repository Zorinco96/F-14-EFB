from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class Method(str, Enum):
    DIRECT_TABLE = "DIRECT_TABLE"
    INTERPOLATED = "INTERPOLATED"
    EXTRAPOLATED = "EXTRAPOLATED"
    CALIBRATED = "CALIBRATED"
    ESTIMATED = "ESTIMATED"


_RANK = {
    Method.DIRECT_TABLE: 0,
    Method.INTERPOLATED: 1,
    Method.CALIBRATED: 2,
    Method.EXTRAPOLATED: 3,
    Method.ESTIMATED: 4,
}


@dataclass(frozen=True)
class Provenance:
    method: Method
    source: str
    detail: str = ""
    confidence: str = ""

    @property
    def label(self) -> str:
        return self.method.value.replace("_", " ").title()


def worst_method(methods: Iterable[Method]) -> Method:
    methods = list(methods)
    if not methods:
        return Method.ESTIMATED
    return max(methods, key=lambda m: _RANK[m])


def combine(*items: Provenance, source: str = "Combined model") -> Provenance:
    valid = [x for x in items if x is not None]
    method = worst_method(x.method for x in valid)
    details = "; ".join(x.detail for x in valid if x.detail)
    confidence = {
        Method.DIRECT_TABLE: "High within tabulated point",
        Method.INTERPOLATED: "Medium-high within source grid",
        Method.CALIBRATED: "Medium; calibrated to DCS observations",
        Method.EXTRAPOLATED: "Low-medium outside source grid",
        Method.ESTIMATED: "Low-medium; physics/model estimate",
    }[method]
    return Provenance(method, source, details, confidence)
