from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from .aero import F14AeroModel, G_FTPS2
from .atmosphere import atmosphere, ias_to_tas_kt, isa_temperature_c, mach_from_tas
from .engine import F110Deck
from .provenance import Method, Provenance
from .types import EnergyResult


KG_M3_TO_SLUG_FT3 = 0.00194032033
KT_TO_FPS = 1.68780986


def _turn_metrics(n: float, tas_fps: float) -> tuple[float, float]:
    if n <= 1.0001:
        return 0.0, float("inf")
    root = math.sqrt(n * n - 1.0)
    rate_rad_s = G_FTPS2 * root / max(1.0, tas_fps)
    radius = tas_fps * tas_fps / (G_FTPS2 * root)
    return math.degrees(rate_rad_s), radius


class EnergyModel:
    def __init__(self, data_dir: Path | str | None = None):
        self.engine = F110Deck(data_dir)
        self.aero = F14AeroModel()

    def calculate(
        self,
        weight_lb: float,
        altitude_ft: float,
        ias_kt: float,
        drag_index: float = 0.0,
        planning_g_limit: float = 6.5,
        power: str = "MIL",
        isa_delta_c: float = 0.0,
    ) -> EnergyResult:
        oat = isa_temperature_c(altitude_ft) + isa_delta_c
        atm = atmosphere(altitude_ft, oat)
        tas_kt = ias_to_tas_kt(ias_kt, atm["sigma"])
        tas_fps = tas_kt * KT_TO_FPS
        mach = mach_from_tas(tas_kt, atm["speed_of_sound_kt"])
        rho_slug = atm["rho_kg_m3"] * KG_M3_TO_SLUG_FT3
        eng = self.engine.total(altitude_ft, mach, mode="AB" if power.upper() == "AB" else "MIL", rpm_pct=100, oat_c=oat)
        level = self.aero.point(weight_lb, rho_slug, tas_fps, mach, "CLEAN", 1.0, drag_index)
        ps = tas_fps * (eng.thrust_lbf_per_engine - level.drag_lbf) / max(1.0, weight_lb)

        lift_g = self.aero.max_lift_g(weight_lb, rho_slug, tas_fps, mach, "CLEAN")
        inst_g = max(1.0, min(float(planning_g_limit), lift_g))
        inst_rate, inst_radius = _turn_metrics(inst_g, tas_fps)

        sustained_g = 1.0
        for n in np.arange(1.0, inst_g + 0.001, 0.05):
            point = self.aero.point(weight_lb, rho_slug, tas_fps, mach, "CLEAN", float(n), drag_index)
            if point.drag_lbf <= eng.thrust_lbf_per_engine:
                sustained_g = float(n)
            else:
                break
        sus_rate, sus_radius = _turn_metrics(sustained_g, tas_fps)
        return EnergyResult(
            speed_ias_kt=round(ias_kt, 1),
            mach=round(mach, 3),
            ps_fps=round(ps, 1),
            instantaneous_g=round(inst_g, 2),
            instantaneous_turn_rate_dps=round(inst_rate, 2),
            instantaneous_radius_ft=round(inst_radius) if math.isfinite(inst_radius) else float("inf"),
            sustained_g=round(sustained_g, 2),
            sustained_turn_rate_dps=round(sus_rate, 2),
            sustained_radius_ft=round(sus_radius) if math.isfinite(sus_radius) else float("inf"),
            provenance=Provenance(
                Method.ESTIMATED,
                "Energy-maneuverability estimate",
                "Low-order polar + F110 deck; planning G limit is user-selected and not asserted as a NATOPS structural limit",
                "Low-medium; useful for DCS trend comparison and calibration",
            ),
        )
