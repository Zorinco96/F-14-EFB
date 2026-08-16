from __future__ import annotations

import math
from pathlib import Path

from .aero import G_FTPS2
from .atmosphere import atmosphere, cas_to_mach, isa_temperature_c
from .provenance import Method, Provenance
from .types import EnergyResult


KT_TO_FPS = 1.68780986


class EnergyModel:
    """Level-turn geometry without an unverified sustained-performance claim."""

    def __init__(self, data_dir: Path | str | None = None):
        _ = data_dir

    def calculate(
        self,
        weight_lb: float,
        altitude_ft: float,
        ias_kt: float,
        drag_index: float = 0.0,
        planning_g_limit: float = 4.0,
        power: str = "MIL",
        isa_delta_c: float = 0.0,
    ) -> EnergyResult:
        _ = (weight_lb, drag_index, power)
        oat = isa_temperature_c(altitude_ft) + isa_delta_c
        atm = atmosphere(altitude_ft, oat)
        mach = cas_to_mach(ias_kt, atm["pressure_pa"])
        tas_kt = mach * atm["speed_of_sound_kt"]
        tas_fps = tas_kt * KT_TO_FPS
        planning_g = max(1.01, float(planning_g_limit))
        root = math.sqrt(planning_g * planning_g - 1.0)
        rate_dps = math.degrees(G_FTPS2 * root / max(1.0, tas_fps))
        radius_ft = tas_fps * tas_fps / (G_FTPS2 * root)
        return EnergyResult(
            speed_ias_kt=round(ias_kt),
            speed_tas_kt=round(tas_kt),
            mach=round(mach, 3),
            planning_g=round(planning_g, 1),
            turn_rate_dps=round(rate_dps, 1),
            turn_radius_ft=round(radius_ft),
            turn_180_sec=round(180.0 / rate_dps, 1),
            turn_360_sec=round(360.0 / rate_dps, 1),
            provenance=Provenance(
                Method.ESTIMATED,
                "Coordinated level-turn geometry",
                "Kinematic speed/G calculation only; no Ps, lift-limit, or sustained-turn prediction",
                "High for idealized geometry; does not establish aircraft capability",
            ),
        )
