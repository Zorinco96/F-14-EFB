from __future__ import annotations

import math
from pathlib import Path

from .aero import F14AeroModel
from .atmosphere import atmosphere, mach_to_cas_kt
from .data import read_csv, require_columns
from .engine import F110Deck
from .interpolate import regular_grid_interpolate
from .provenance import Method, Provenance, combine
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
        raw_altitude = alt.value
        altitude = int(math.floor(raw_altitude / 1000.0 + 0.5) * 1000)
        m = mach.value
        oat = 15.0 - 1.9812 * altitude / 1000.0 + isa_delta_c
        atm = atmosphere(altitude, oat)
        tas_kt = m * atm["speed_of_sound_kt"]
        ias_kt = mach_to_cas_kt(m, atm["pressure_pa"])
        rho_slug = atm["rho_kg_m3"] * KG_M3_TO_SLUG_FT3
        aero = self.aero.point(
            weight_lb, rho_slug, tas_kt * KT_TO_FPS, m, "CLEAN", 1.0, drag_index
        )

        selected = None
        for rpm in range(70, 101):
            p = self.engine.point(altitude, m, mode="MIL", rpm_pct=rpm, oat_c=oat)
            if p.thrust_lbf_per_engine * 2.0 >= aero.drag_lbf:
                selected = p
                break
        if selected is None:
            selected = self.engine.point(altitude, m, mode="MIL", rpm_pct=100.0, oat_c=oat)
        # The engine/drag model is not a cockpit calibration.  Round the first
        # modeled equilibrium point upward to a usable 5-percent initial power
        # setting, then round fuel flow upward to a 250-PPH planning increment.
        # This avoids presenting a minimum one-percent solution as an exact DCS
        # setting and keeps the fuel estimate on the cautious side.
        planning_rpm = min(100.0, math.ceil(selected.rpm_pct / 5.0) * 5.0)
        planning_point = self.engine.point(
            altitude, m, mode="MIL", rpm_pct=planning_rpm, oat_c=oat
        )
        ff_per_engine = max(
            250.0,
            math.ceil(planning_point.fuel_flow_pph_per_engine / 250.0) * 250.0,
        )
        total_ff = ff_per_engine * 2.0
        specific_range = tas_kt / total_ff * 1000.0
        endurance = 1000.0 / total_ff
        table_prov = Provenance(
            Method.ESTIMATED,
            "Unverified legacy f14_cruise_natops.csv trial table",
            f"Weight/drag-index interpolation; raw altitude {raw_altitude:.0f} ft rounded to a usable flight level; source note: {self.df['source_note'].iloc[0]}",
            "Low; the prior 01-F14AAP-1B page citation was invalid and has been removed",
        )
        estimate_prov = Provenance(
            Method.ESTIMATED,
            "Aero/engine cruise fuel model",
            f"Estimated required thrust met near {selected.rpm_pct:.0f}% dry RPM; initial setting rounded up to {planning_rpm:.0f}% and fuel flow rounded up to 250 PPH/engine",
            "Low-medium for fuel flow and specific range",
        )
        return CruiseResult(
            optimum_altitude_ft=round(altitude),
            flight_level=round(altitude / 100),
            optimum_mach=round(m, 2),
            optimum_ias_kt=round(ias_kt / 5.0) * 5,
            tas_kt=round(tas_kt),
            rpm_pct=round(planning_rpm),
            fuel_flow_pph_per_engine=round(ff_per_engine),
            specific_range_nm_per_1000lb=round(specific_range, 1),
            endurance_hr_per_1000lb=round(endurance, 2),
            provenance=combine(table_prov, estimate_prov, source="Legacy cruise trial solution"),
            notes=[
                "Legacy trial altitude is rounded to the nearest 1,000 ft usable flight level; it is not a verified optimum.",
                "NATOPS Figure 14-1 lists 8 units AOA at optimum cruise altitude only as an alternate cue following an airspeed-indicator failure; it does not validate this table's altitude or Mach values.",
                "KIAS is atmosphere-derived. RPM is a modeled cross-check rounded up to 5%; fuel flow per engine is a trial planning allowance rounded up to 250 PPH.",
                "Specific range and endurance use the two-engine aircraft fuel flow.",
            ],
        )
