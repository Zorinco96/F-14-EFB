from __future__ import annotations

import math
from pathlib import Path

from .atmosphere import pressure_altitude_ft
from .data import read_csv, require_columns
from .interpolate import regular_grid_interpolate
from .provenance import Method, Provenance, combine
from .types import Environment, LandingFuelReference, LandingResult, Runway
from .weather import wind_components


class LandingModel:
    FIELD_LANDING_LIMIT_LB = 60_000.0
    CARRIER_LANDING_LIMIT_LB = 54_000.0
    USABLE_FUEL_LB = 20_000.0
    REQUIRED = {
        "flap_setting", "gross_weight_lbs", "pressure_alt_ft", "temp_f",
        "headwind_kt", "ground_roll_ft_unfactored",
    }

    def __init__(self, data_dir: Path | str | None = None):
        self.df = read_csv("f14_landing_natops_full.csv", data_dir)
        self.df.columns = [str(c).strip().lower() for c in self.df.columns]
        require_columns(self.df, self.REQUIRED, "f14_landing_natops_full.csv")
        self.df["flap_setting"] = self.df["flap_setting"].astype(str).str.upper()

    def calculate(
        self,
        weight_lb: float,
        environment: Environment,
        runway: Runway,
        flaps: str = "DOWN",
        planning_factor: float = 1.10,
        carrier: bool = False,
    ) -> LandingResult:
        flap = flaps.upper()
        sub = self.df[self.df["flap_setting"] == flap]
        if sub.empty:
            raise ValueError(f"No landing table available for flap setting {flap}")
        field_elev = runway.elevation_ft if runway.elevation_ft is not None else environment.field_elevation_ft
        pa = pressure_altitude_ft(field_elev, environment.qnh_inhg)
        headwind, _ = wind_components(environment.wind_dir_deg, environment.wind_speed_kt, runway.heading_deg)
        temp_f = environment.oat_c * 9.0 / 5.0 + 32.0
        lookup = regular_grid_interpolate(
            sub,
            {
                "gross_weight_lbs": weight_lb,
                "pressure_alt_ft": pa,
                "temp_f": temp_f,
                "headwind_kt": headwind,
            },
            "ground_roll_ft_unfactored",
        )
        ground_roll = lookup.value
        correction_prov = None
        warnings: list[str] = []
        if runway.condition.upper() == "WET":
            ground_roll *= 1.20
            correction_prov = Provenance(
                Method.ESTIMATED,
                "Wet landing correction",
                "20% ground-roll increase applied",
                "Low-medium; explicit planning estimate",
            )
            warnings.append("Wet landing correction is estimated, not a released F-14B chart factor.")
        factored = ground_roll * planning_factor
        margin = runway.asda_ft - factored
        if margin < 0:
            warnings.append(f"Factored landing ground roll exceeds available runway by {abs(margin):.0f} ft.")
        if carrier and weight_lb > 54000:
            warnings.append("Carrier landing weight exceeds the 54,000 lb maximum trap weight documented by Heatblur.")

        on_speed = 133.0 * math.sqrt(max(0.4, weight_lb / 54000.0))
        table_prov = Provenance(
            lookup.method,
            "Legacy f14_landing_natops_full.csv",
            f"4-D landing ground-roll lookup: {lookup.detail}",
            "Medium-high inside legacy table grid; source transcription not independently re-digitized in v3",
        )
        aoa_prov = Provenance(
            Method.ESTIMATED,
            "Heatblur 15-unit on-speed reference + v3 IAS estimate",
            "On-speed AOA is documented; IAS scales with square root of landing weight from a 54,000 lb calibration point",
            "AOA high confidence; IAS estimate low-medium",
        )
        prov = combine(table_prov, correction_prov, aoa_prov, source="Landing solution")
        return LandingResult(
            ground_roll_ft=round(ground_roll),
            factored_distance_ft=round(factored),
            on_speed_aoa_units=15.0,
            on_speed_ias_est_kt=round(on_speed, 1),
            runway_margin_ft=round(margin),
            provenance=prov,
            warnings=warnings,
        )

    def fuel_reference(
        self,
        takeoff_weight_lb: float,
        starting_fuel_lb: float,
        expendable_credit_lb: float = 0.0,
    ) -> LandingFuelReference:
        retained_zfw = max(0.0, float(takeoff_weight_lb) - float(starting_fuel_lb))
        credit = max(0.0, float(expendable_credit_lb))
        expended_zfw = max(0.0, retained_zfw - credit)

        def available(limit: float, zfw: float) -> float:
            value = max(0.0, min(self.USABLE_FUEL_LB, limit - zfw))
            return math.floor(value / 100.0) * 100.0

        return LandingFuelReference(
            field_limit_lb=self.FIELD_LANDING_LIMIT_LB,
            carrier_limit_lb=self.CARRIER_LANDING_LIMIT_LB,
            retained_zero_fuel_weight_lb=round(retained_zfw),
            expendable_credit_lb=round(credit),
            field_retained_fuel_lb=available(self.FIELD_LANDING_LIMIT_LB, retained_zfw),
            field_expended_fuel_lb=available(self.FIELD_LANDING_LIMIT_LB, expended_zfw),
            carrier_retained_fuel_lb=available(self.CARRIER_LANDING_LIMIT_LB, retained_zfw),
            carrier_expended_fuel_lb=available(self.CARRIER_LANDING_LIMIT_LB, expended_zfw),
            provenance=Provenance(
                Method.ESTIMATED,
                "F-14 landing gross-weight limits + entered mission weight",
                "60,000 lb field and 54,000 lb carrier limits; selected-store expendable credit rounded down; results rounded down to 100 lb",
                "Conservative quick reference; verify actual DCS gross weight before recovery",
            ),
            notes=[
                "All-stores-retained values use takeoff gross weight minus starting fuel as retained zero-fuel weight.",
                "Expended values credit only selected weapons with a defined conservative expendable weight. Tanks, pods, racks, adapters, and unknown stores remain retained.",
            ],
        )
