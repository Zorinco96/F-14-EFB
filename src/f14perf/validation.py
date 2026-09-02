from __future__ import annotations

from pathlib import Path

import pandas as pd

from .aircraft import AircraftState, INTERNAL_FUEL_CAPACITY_LB
from .climb import ClimbModel
from .cruise import CruiseModel
from .data import DEFAULT_DATA_DIR
from .landing import LandingModel
from .loadout import loadout_from_preset
from .takeoff import AutoTakeoffSelector
from .types import Environment, Runway, TakeoffInputs


def _status(result) -> str:
    if not result.takeoff_data_valid:
        return "PLANNING_HOLD"
    if not result.feasible:
        return "LIMIT_EXCEEDED"
    return "REFERENCE_ONLY"


def run_validation_battery(
    data_dir: Path | str | None = None,
    scenario_file: Path | str | None = None,
) -> pd.DataFrame:
    """Run the maintained scenario matrix through one synchronized state."""

    data_path = Path(data_dir) if data_dir is not None else DEFAULT_DATA_DIR
    cases_path = Path(scenario_file) if scenario_file is not None else data_path / "validation_scenarios.csv"
    cases = pd.read_csv(cases_path)
    takeoff_model = AutoTakeoffSelector(data_dir)
    climb_model = ClimbModel(data_dir)
    cruise_model = CruiseModel(data_dir)
    landing_model = LandingModel(data_dir)
    outcomes: list[dict[str, object]] = []

    for case in cases.itertuples(index=False):
        variant = str(case.variant)
        environment = Environment(
            field_elevation_ft=float(case.elevation_ft),
            oat_c=float(case.oat_c),
            qnh_inhg=float(case.qnh_inhg),
            wind_dir_deg=None if pd.isna(case.wind_dir_deg) else float(case.wind_dir_deg),
            wind_speed_kt=float(case.wind_speed_kt),
        )
        runway = Runway(
            name=str(case.case_id),
            heading_deg=0.0,
            tora_ft=float(case.runway_ft),
            toda_ft=float(case.runway_ft),
            asda_ft=float(case.runway_ft),
            elevation_ft=float(case.elevation_ft),
            condition=str(case.condition),
        )
        loadout = loadout_from_preset(str(case.loadout_preset), variant=variant)
        initial_aircraft = AircraftState(
            variant=variant,
            loadout=loadout,
            internal_fuel_lb=INTERNAL_FUEL_CAPACITY_LB,
            external_fuel_lb=loadout.external_fuel_capacity_lb,
            gross_weight_override_lb=float(case.weight_lb),
        )
        recovery_fuel = max(
            0.0,
            min(
                initial_aircraft.recovery_fuel_capacity_lb,
                float(case.landing_weight_lb) - initial_aircraft.recovery_zero_fuel_weight_lb,
            ),
        )
        aircraft = initial_aircraft.with_recovery_fuel(recovery_fuel)
        rating = str(case.thrust_rating)
        is_auto = rating.upper() == "AUTO"
        takeoff_inputs = TakeoffInputs(
            weight_lb=aircraft.launch_gross_weight_lb,
            environment=environment,
            runway=runway,
            flaps=str(case.flaps),
            thrust="AUTO" if is_auto else "MANUAL",
            thrust_rating=None if is_auto else rating,
            takeoff_loadout=aircraft.loadout.station_summary,
        )
        takeoff = takeoff_model.select(takeoff_inputs)
        cruise = cruise_model.optimum(
            aircraft.launch_gross_weight_lb,
            aircraft.launch_drag_index,
        )
        climb = climb_model.profile(
            aircraft.launch_gross_weight_lb,
            drag_index=aircraft.launch_drag_index,
            end_alt_ft=int(cruise.optimum_altitude_ft),
            strategy="MINIMUM_TIME",
        )
        landing = landing_model.calculate(
            aircraft.expected_recovery_gross_weight_lb,
            environment,
            runway,
            carrier_limit_lb=aircraft.definition.carrier_landing_limit_lb,
        )
        actual_status = _status(takeoff)
        outcomes.append(
            {
                "case_id": case.case_id,
                "aircraft_state_id": aircraft.config_id,
                "variant": variant,
                "reference_class": case.reference_class,
                "expected_status": case.expected_status,
                "actual_status": actual_status,
                "status_match": actual_status == case.expected_status,
                "calculated_launch_weight_lb": aircraft.calculated_launch_gross_weight_lb,
                "launch_weight_override_lb": aircraft.launch_gross_weight_lb,
                "launch_zero_fuel_weight_lb": aircraft.launch_zero_fuel_weight_lb,
                "launch_fuel_lb": aircraft.total_launch_fuel_lb,
                "launch_drag_index": aircraft.launch_drag_index,
                "launch_drag_valid": aircraft.loadout.drag_data_valid,
                "recovery_zero_fuel_weight_lb": aircraft.recovery_zero_fuel_weight_lb,
                "recovery_fuel_lb": aircraft.expected_recovery_fuel_lb,
                "recovery_gross_weight_lb": aircraft.expected_recovery_gross_weight_lb,
                "recovery_drag_index": aircraft.recovery_drag_index,
                "flaps": takeoff.flaps,
                "rating": takeoff.thrust_setting,
                "ff_pph_per_engine": takeoff.fuel_flow_pph_per_engine,
                "rpm_reference": takeoff.rpm_reference,
                "vr_kt": takeoff.vr_kt,
                "v2_kt": takeoff.v2_kt,
                "trim_anu": takeoff.stabilizer_trim_anu,
                "takeoff_distance_ft": takeoff.factored_agd_ft,
                "runway_margin_ft": takeoff.toda_margin_ft,
                "climb_time_min": climb.time_min,
                "climb_distance_nm": climb.distance_nm,
                "climb_fuel_lb": climb.fuel_burn_lb,
                "cruise_fl": cruise.flight_level,
                "cruise_mach": cruise.optimum_mach,
                "cruise_ff_pph_per_engine": cruise.fuel_flow_pph_per_engine,
                "cruise_rpm_pct": cruise.rpm_pct,
                "landing_ground_roll_ft": landing.ground_roll_ft,
                "landing_on_speed_ias_kt": landing.on_speed_ias_est_kt,
            }
        )

    return pd.DataFrame(outcomes)
