from __future__ import annotations

from pathlib import Path

from .aero import F14AeroModel
from .atmosphere import atmosphere
from .data import read_csv, require_columns
from .engine import F110Deck
from .interpolate import regular_grid_interpolate
from .provenance import Method, Provenance, combine, worst_method
from .types import CruiseResult


KG_M3_TO_SLUG_FT3 = 0.00194032033
KT_TO_FPS = 1.68780986


class CruiseModel:
    REQUIRED = {"gross_weight_lbs", "drag_index", "optimum_alt_ft", "optimum_mach", "source_note"}

    def __init__(self, data_dir: Path | str | None = None):
        self.df = read_csv("f14_cruise_natops.csv", data_dir)
        self.df.columns = [str(c).strip().lower() for c in self.df.columns]
        require_columns(self.df, self.REQUIRED, "f14_cruise_natops.csv")
        self.engine = F110Deck(data_dir)
        self.aero = F14AeroModel()

    def optimum(self, weight_lb: float, drag_index: float = 0.0, isa_delta_c: float = 0.0) -> CruiseResult:
        axes = {"gross_weight_lbs": weight_lb, "drag_index": drag_index}
        alt = regular_grid_interpolate(self.df, axes, "optimum_alt_ft")
        mach = regular_grid_interpolate(self.df, axes, "optimum_mach")
        altitude = alt.value
        m = mach.value
        oat = 15.0 - 1.9812 * altitude / 1000.0 + isa_delta_c
        atm = atmosphere(altitude, oat)
        tas_kt = m * atm["speed_of_sound_kt"]
        rho_slug = atm["rho_kg_m3"] * KG_M3_TO_SLUG_FT3
        aero = self.aero.point(
            weight_lb, rho_slug, tas_kt * KT_TO_FPS, m, "CLEAN", 1.0, drag_index
        )

        selected = None
        for rpm in range(70, 101):
            p = self.engine.total(altitude, m, mode="MIL", rpm_pct=rpm, oat_c=oat)
            if p.thrust_lbf_per_engine >= aero.drag_lbf:
                selected = p
                break
        if selected is None:
            selected = self.engine.total(altitude, m, mode="MIL", rpm_pct=100.0, oat_c=oat)
        ff = max(1.0, selected.fuel_flow_pph_per_engine)
        specific_range = tas_kt / ff * 1000.0
        endurance = 1000.0 / ff
        table_method = worst_method([alt.method, mach.method])
        table_prov = Provenance(
            table_method,
            "Legacy f14_cruise_natops.csv optimum-altitude table",
            f"Weight/drag-index interpolation; source note: {self.df['source_note'].iloc[0]}",
            "Medium-high for optimum altitude/Mach inside table; original digitization not re-verified in v3",
        )
        estimate_prov = Provenance(
            Method.ESTIMATED,
            "Aero/engine cruise fuel model",
            f"Estimated required thrust met near {selected.rpm_pct:.0f}% dry RPM",
            "Low-medium for fuel flow and specific range",
        )
        return CruiseResult(
            optimum_altitude_ft=round(altitude),
            optimum_mach=round(m, 3),
            tas_kt=round(tas_kt),
            fuel_flow_pph_total=round(ff),
            specific_range_nm_per_1000lb=round(specific_range, 2),
            endurance_hr_per_1000lb=round(endurance, 3),
            provenance=combine(table_prov, estimate_prov, source="Cruise solution"),
            notes=[
                "Optimum altitude/Mach comes from the legacy table when within its grid.",
                "Fuel flow and specific range are model estimates using the F110 deck and low-order drag polar.",
            ],
        )
