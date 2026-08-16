from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from .provenance import Method


@dataclass(frozen=True)
class InterpResult:
    value: float
    method: Method
    detail: str


def _bracket(values: Sequence[float], x: float) -> tuple[float, float, float, Method]:
    vals = np.array(sorted({float(v) for v in values}), dtype=float)
    if len(vals) == 0:
        raise ValueError("Cannot interpolate an empty axis")
    if len(vals) == 1:
        return vals[0], vals[0], 0.0, Method.DIRECT_TABLE
    if np.isclose(x, vals).any():
        v = float(vals[np.argmin(abs(vals - x))])
        return v, v, 0.0, Method.DIRECT_TABLE
    if x < vals[0]:
        lo, hi = vals[0], vals[1]
        return lo, hi, (x - lo) / (hi - lo), Method.EXTRAPOLATED
    if x > vals[-1]:
        lo, hi = vals[-2], vals[-1]
        return lo, hi, (x - lo) / (hi - lo), Method.EXTRAPOLATED
    hi_i = int(np.searchsorted(vals, x))
    lo, hi = vals[hi_i - 1], vals[hi_i]
    return lo, hi, (x - lo) / (hi - lo), Method.INTERPOLATED


def regular_grid_interpolate(
    df: pd.DataFrame,
    axes: Mapping[str, float],
    value_col: str,
) -> InterpResult:
    """Multilinear interpolation on a complete or near-complete rectangular grid."""
    work = df.copy()
    brackets: dict[str, tuple[float, float, float, Method]] = {}
    methods: list[Method] = []
    for axis, target in axes.items():
        b = _bracket(work[axis].dropna().unique(), float(target))
        brackets[axis] = b
        methods.append(b[3])

    corner_axes = []
    for axis, (lo, hi, _, _) in brackets.items():
        corner_axes.append((axis, [lo] if np.isclose(lo, hi) else [lo, hi]))

    weighted = 0.0
    weight_sum = 0.0
    missing_corners = 0
    for choices in product(*[values for _, values in corner_axes]):
        selector = pd.Series(True, index=work.index)
        weight = 1.0
        for (axis, _), choice in zip(corner_axes, choices):
            lo, hi, t, _ = brackets[axis]
            selector &= np.isclose(work[axis].astype(float), float(choice))
            if not np.isclose(lo, hi):
                weight *= t if np.isclose(choice, hi) else 1.0 - t
        rows = work.loc[selector]
        if rows.empty:
            missing_corners += 1
            continue
        value = float(rows[value_col].astype(float).mean())
        weighted += weight * value
        weight_sum += weight

    if weight_sum <= 1e-12:
        numeric = work[list(axes)].astype(float)
        spans = numeric.max() - numeric.min()
        spans = spans.replace(0, 1.0)
        dist2 = sum(((numeric[k] - float(v)) / spans[k]) ** 2 for k, v in axes.items())
        nearest = work.assign(_d2=dist2).nsmallest(min(8, len(work)), "_d2")
        if nearest.empty:
            raise ValueError(f"No data available for {value_col}")
        if float(nearest.iloc[0]["_d2"]) < 1e-12:
            value = float(nearest.iloc[0][value_col])
        else:
            weights = 1.0 / np.maximum(nearest["_d2"].to_numpy(float), 1e-9)
            value = float(np.average(nearest[value_col].to_numpy(float), weights=weights))
        method = Method.ESTIMATED
        return InterpResult(value, method, "Sparse-grid inverse-distance fallback")

    value = weighted / weight_sum
    if Method.EXTRAPOLATED in methods:
        method = Method.EXTRAPOLATED
    elif Method.INTERPOLATED in methods or missing_corners:
        method = Method.INTERPOLATED if not missing_corners else Method.ESTIMATED
    else:
        method = Method.DIRECT_TABLE
    detail = "Multilinear grid lookup"
    if missing_corners:
        detail += f"; {missing_corners} missing corner(s) renormalized"
    return InterpResult(float(value), method, detail)
