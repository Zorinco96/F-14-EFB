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
    USABLE_FUEL_LB = 19_800.0
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
        planning_factor: float = 1.15,
        carrier: bool = False,
        carrier_limit_lb: float | None = None,
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
        effective_carrier_limit = (
            self.CARRIER_LANDING_LIMIT_LB
            if carrier_limit_lb is None
            else float(carrier_limit_lb)
        )
        if carrier and weight_lb > effective_carrier_limit:
            warnings.append(
                f"Carrier landing weight exceeds the {effective_carrier_limit:,.0f} lb planning limit for the selected variant."
            )

        # NAVAIR 01-F14AAP-1, Figure 11-8 is a flight-test chart for 15 units
        # AOA, 20-degree wing sweep, and all drag indexes.  The two plotted
        # lines are nearly linear from 40,000 through 60,000 lb.  Digitizing
        # those lines is materially better than the former square-root estimate,
        # which understated the normal DLC-neutral reference by about 7 kt at
        # 54,000 lb.
        on_speed_dlc_neutral = 118.0 + 1.55 * ((weight_lb - 40_000.0) / 1_000.0)
        on_speed_dlc_stowed = 111.0 + 1.40 * ((weight_lb - 40_000.0) / 1_000.0)
        if not 40_000.0 <= weight_lb <= 60_000.0:
            warnings.append(
                "Landing on-speed IAS is outside the 40,000 to 60,000 lb Figure 11-8 chart range."
            )
        table_prov = Provenance(
            lookup.method,
            "Legacy f14_landing_natops_full.csv",
            f"4-D landing ground-roll lookup: {lookup.detail}",
            "Medium-high inside legacy table grid; source transcription not independently re-digitized in v3",
        )
        approach_method = (
            Method.CALIBRATED
            if 40_000.0 <= weight_lb <= 60_000.0
            else Method.EXTRAPOLATED
        )
        aoa_prov = Provenance(
            approach_method,
            "NAVAIR 01-F14AAP-1 Figure 11-8 flight-test chart",
            "15 units AOA; wing sweep 20 degrees; all drag indexes; DLC-neutral and DLC-stowed lines digitized; chart IAS tolerance +/-4 kt",
            "High for AOA and medium-high for chart-read IAS inside 40,000 to 60,000 lb",
        )
        prov = combine(table_prov, correction_prov, aoa_prov, source="Landing solution")
        return LandingResult(
            ground_roll_ft=round(ground_roll),
            factored_distance_ft=round(factored),
            on_speed_aoa_units=15.0,
            on_speed_ias_est_kt=round(on_speed_dlc_neutral, 1),
            on_speed_ias_dlc_stowed_kt=round(on_speed_dlc_stowed, 1),
            on_speed_ias_tolerance_kt=4.0,
            runway_margin_ft=round(margin),
            provenance=prov,
            warnings=warnings,
        )

    def fuel_reference(
        self,
        takeoff_weight_lb: float | None = None,
        starting_fuel_lb: float | None = None,
        expendable_credit_lb: float = 0.0,
        *,
        launch_zero_fuel_weight_lb: float | None = None,
        recovery_zero_fuel_weight_lb: float | None = None,
        launch_fuel_capacity_lb: float | None = None,
        recovery_fuel_capacity_lb: float | None = None,
        field_limit_lb: float | None = None,
        carrier_limit_lb: float | None = None,
    ) -> LandingFuelReference:
        """Return retained and planned-recovery maximum-fuel references.

        The authoritative path passes launch and recovery zero-fuel weights from
        ``AircraftState``. The first three arguments remain only for callers
        that have not yet migrated; they are converted to the same relationship.
        """

        if launch_zero_fuel_weight_lb is None:
            if takeoff_weight_lb is None or starting_fuel_lb is None:
                raise ValueError(
                    "Provide AircraftState zero-fuel weights or legacy takeoff weight and starting fuel"
                )
            launch_zfw = max(0.0, float(takeoff_weight_lb) - float(starting_fuel_lb))
        else:
            launch_zfw = max(0.0, float(launch_zero_fuel_weight_lb))

        if recovery_zero_fuel_weight_lb is None:
            credit = max(0.0, float(expendable_credit_lb))
            recovery_zfw = max(0.0, launch_zfw - credit)
        else:
            recovery_zfw = max(0.0, float(recovery_zero_fuel_weight_lb))
            credit = max(0.0, launch_zfw - recovery_zfw)

        field_limit = self.FIELD_LANDING_LIMIT_LB if field_limit_lb is None else float(field_limit_lb)
        carrier_limit = self.CARRIER_LANDING_LIMIT_LB if carrier_limit_lb is None else float(carrier_limit_lb)
        launch_capacity = self.USABLE_FUEL_LB if launch_fuel_capacity_lb is None else float(launch_fuel_capacity_lb)
        recovery_capacity = launch_capacity if recovery_fuel_capacity_lb is None else float(recovery_fuel_capacity_lb)

        def available(limit: float, zfw: float, capacity: float) -> float:
            value = max(0.0, min(capacity, limit - zfw))
            return math.floor(value / 100.0) * 100.0

        return LandingFuelReference(
            field_limit_lb=field_limit,
            carrier_limit_lb=carrier_limit,
            retained_zero_fuel_weight_lb=round(launch_zfw),
            expendable_credit_lb=round(credit),
            field_retained_fuel_lb=available(field_limit, launch_zfw, launch_capacity),
            field_expended_fuel_lb=available(field_limit, recovery_zfw, recovery_capacity),
            carrier_retained_fuel_lb=available(carrier_limit, launch_zfw, launch_capacity),
            carrier_expended_fuel_lb=available(carrier_limit, recovery_zfw, recovery_capacity),
            provenance=Provenance(
                Method.ESTIMATED,
                "F-14 landing limits + synchronized AircraftState",
                f"{field_limit:,.0f} lb field limit; {carrier_limit:,.0f} lb variant carrier/FCLP limit; station-level recovery disposition; retained fuel-system capacity; results rounded down to 100 lb",
                "Conservative quick reference; verify actual DCS gross weight before recovery",
            ),
            notes=[
                "Retained values use the synchronized launch zero-fuel weight and selected launch fuel capacity.",
                "Expected-recovery values use station-level retained, expended, and jettisoned selections plus the fuel capacity remaining after planned tank jettison.",
                f"The selected variant uses a {carrier_limit:,.0f} lb carrier/FCLP planning limit.",
            ],
        )
