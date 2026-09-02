from __future__ import annotations

from pathlib import Path

from .aircraft import AircraftState
from .climb import ClimbModel
from .cruise import CruiseModel
from .fuel import FuelModel
from .landing import LandingModel
from .takeoff import AutoTakeoffSelector
from .types import Environment, MissionCard, Runway, TakeoffInputs


class MissionPlanner:
    def __init__(self, data_dir: Path | str | None = None):
        self.takeoff = AutoTakeoffSelector(data_dir)
        self.climb = ClimbModel(data_dir)
        self.cruise = CruiseModel(data_dir)
        self.landing = LandingModel(data_dir)
        self.fuel = FuelModel()

    def build_for_aircraft(
        self,
        aircraft: AircraftState,
        environment: Environment,
        runway: Runway,
        route_nm: float,
        bingo_lb: float,
        joker_margin_lb: float,
        *,
        flaps: str = "UP",
        thrust_rating: str = "AUTO",
        runway_factor: float = 1.15,
        climb_target_ft_nm: float = 300.0,
        headwind_credit_pct: float = 0.0,
        tailwind_penalty_pct: float = 150.0,
        isa_delta_c: float = 0.0,
        climb_strategy: str = "MINIMUM_TIME",
    ) -> MissionCard:
        """Build all phases from one immutable aircraft state."""

        is_auto = thrust_rating.upper() == "AUTO"
        takeoff_inputs = TakeoffInputs(
            weight_lb=aircraft.launch_gross_weight_lb,
            environment=environment,
            runway=runway,
            flaps=flaps,
            thrust="AUTO" if is_auto else "MANUAL",
            thrust_rating=None if is_auto else thrust_rating,
            runway_factor=runway_factor,
            climb_target_ft_nm=climb_target_ft_nm,
            headwind_credit_pct=headwind_credit_pct,
            tailwind_penalty_pct=tailwind_penalty_pct,
            takeoff_loadout=aircraft.loadout.station_summary,
        )
        takeoff = self.takeoff.select(takeoff_inputs)
        cruise = self.cruise.optimum(
            aircraft.launch_gross_weight_lb,
            aircraft.launch_drag_index,
            isa_delta_c,
        )
        climb_profile = self.climb.profile(
            aircraft.launch_gross_weight_lb,
            isa_delta_c=isa_delta_c,
            drag_index=aircraft.launch_drag_index,
            target_gradient_ft_nm=climb_target_ft_nm,
            end_alt_ft=int(cruise.optimum_altitude_ft),
            strategy=climb_strategy,
        )
        fuel = self.fuel.plan(
            aircraft.total_launch_fuel_lb,
            route_nm,
            climb_profile.points,
            cruise,
            bingo_lb,
            joker_margin_lb,
        )
        projected_aircraft = aircraft.with_recovery_fuel(max(0.0, fuel.landing_fuel_lb))
        landing = self.landing.calculate(
            projected_aircraft.expected_recovery_gross_weight_lb,
            environment,
            runway,
            flaps="DOWN",
            planning_factor=runway_factor,
            carrier_limit_lb=aircraft.definition.carrier_landing_limit_lb,
        )
        return MissionCard(
            takeoff=takeoff,
            climb=climb_profile.points,
            cruise=cruise,
            landing=landing,
            fuel=fuel,
            metadata={
                "route_nm": route_nm,
                "aircraft_state_id": projected_aircraft.config_id,
                "variant": aircraft.variant,
                "launch_zero_fuel_weight_lb": aircraft.launch_zero_fuel_weight_lb,
                "launch_gross_weight_lb": aircraft.launch_gross_weight_lb,
                "launch_drag_index": aircraft.launch_drag_index,
                "recovery_zero_fuel_weight_lb": aircraft.recovery_zero_fuel_weight_lb,
                "recovery_gross_weight_lb": projected_aircraft.expected_recovery_gross_weight_lb,
                "recovery_drag_index": aircraft.recovery_drag_index,
                "recovery_fuel_capacity_lb": aircraft.recovery_fuel_capacity_lb,
                "recovery_dispositions": aircraft.loadout.recovery_summary,
                "isa_delta_c": isa_delta_c,
                "model": "F-14 EFB synchronized aircraft state",
                "climb_strategy": climb_profile.strategy,
                "climb_profile_label": climb_profile.label,
                "climb_time_to_cruise_min": climb_profile.time_min,
                "climb_fuel_to_cruise_lb": climb_profile.fuel_burn_lb,
                "climb_distance_to_cruise_nm": climb_profile.distance_nm,
            },
        )

    def build_card(self, *args, **kwargs) -> MissionCard:
        raise RuntimeError(
            "Independent takeoff, landing-weight, fuel, and drag inputs are disabled. "
            "Build an AircraftState and call build_for_aircraft()."
        )
