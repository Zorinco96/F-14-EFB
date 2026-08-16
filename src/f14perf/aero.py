from __future__ import annotations

import math
from dataclasses import dataclass

from .provenance import Method, Provenance


WING_AREA_FT2 = 565.0
G_FTPS2 = 32.174


@dataclass(frozen=True)
class AeroPoint:
    cl: float
    cd: float
    drag_lbf: float
    clmax: float
    provenance: Provenance


class F14AeroModel:
    """Transparent low-order aerodynamic model for interpolation gaps.

    The old f14_aero.csv contains several malformed values, so it is not used as
    an authoritative polar. These coefficients are conservative engineering
    estimates and are explicitly marked ESTIMATED in every output.
    """

    CONFIG = {
        "CLEAN": {"cd0": 0.0185, "k": 0.045, "clmax": 1.55},
        "UP": {"cd0": 0.0230, "k": 0.050, "clmax": 1.60},
        "MANEUVER": {"cd0": 0.0340, "k": 0.052, "clmax": 1.85},
        "FULL": {"cd0": 0.0520, "k": 0.055, "clmax": 2.05},
        "LANDING": {"cd0": 0.0600, "k": 0.058, "clmax": 2.10},
    }

    def coefficients(self, config: str, mach: float) -> tuple[float, float, float]:
        cfg = self.CONFIG.get(config.upper(), self.CONFIG["CLEAN"])
        m = max(0.0, float(mach))
        transonic = max(0.0, m - 0.75)
        cd0 = cfg["cd0"] * (1.0 + 1.5 * transonic ** 2)
        k = cfg["k"] * (1.0 + 0.35 * transonic)
        clmax = cfg["clmax"] * max(0.68, 1.0 - 0.18 * max(0.0, m - 0.6))
        return cd0, k, clmax

    def point(
        self,
        weight_lb: float,
        rho_slug_ft3: float,
        tas_fps: float,
        mach: float,
        config: str = "CLEAN",
        load_factor: float = 1.0,
        drag_index: float = 0.0,
    ) -> AeroPoint:
        cd0, k, clmax = self.coefficients(config, mach)
        cd0 += max(0.0, float(drag_index)) * 0.000035
        q = 0.5 * max(1e-6, rho_slug_ft3) * max(1.0, tas_fps) ** 2
        cl = float(load_factor) * float(weight_lb) / max(1.0, q * WING_AREA_FT2)
        cd = cd0 + k * cl ** 2
        drag = q * WING_AREA_FT2 * cd
        return AeroPoint(
            cl=cl,
            cd=cd,
            drag_lbf=drag,
            clmax=clmax,
            provenance=Provenance(
                Method.ESTIMATED,
                "Low-order F-14 aerodynamic model",
                f"{config.upper()} parabolic polar, Mach {mach:.2f}",
                "Low-medium; suitable for trends and interpolation support",
            ),
        )

    def max_lift_g(self, weight_lb: float, rho_slug_ft3: float, tas_fps: float, mach: float, config: str = "CLEAN") -> float:
        _, _, clmax = self.coefficients(config, mach)
        q = 0.5 * rho_slug_ft3 * tas_fps ** 2
        return max(0.0, q * WING_AREA_FT2 * clmax / max(1.0, weight_lb))
