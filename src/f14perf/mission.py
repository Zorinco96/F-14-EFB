from __future__ import annotations

from pathlib import Path

from .climb import ClimbModel
from .cruise import CruiseModel
from .fuel import FuelModel
from .landing import LandingModel
from .takeoff import AutoTakeoffSelector
from .types import MissionCard, TakeoffInputs


class MissionPlanner:
    def __init__(self, data_dir: Path | str | None = None):
        self.takeoff = AutoTakeoffSelector(data_dir)
        self.climb = ClimbModel(data_dir)
        self.cruise = CruiseModel(data_dir)
        self.landing = LandingModel(data_dir)
        self.fuel = FuelModel()

    def build_card(
        self,
        takeoff_inputs: TakeoffInputs,
        landing_weight_lb: float,
        drag_index: float,
        route_nm: float,
        starting_fuel_lb: float,
        bingo_lb: float,
        joker_margin_lb: float,
        isa_delta_c: float = 0.0,
        climb_strategy: str = "MINIMUM_TIME",
    ) -> MissionCard:
        takeoff = self.takeoff.select(takeoff_inputs)
        cruise = self.cruise.optimum(takeoff_inputs.weight_lb, drag_index, isa_delta_c)
        climb_profile = self.climb.profile(
            takeoff_inputs.weight_lb,
            isa_delta_c=isa_delta_c,
            drag_index=drag_index,
            target_gradient_ft_nm=takeoff_inputs.climb_target_ft_nm,
            end_alt_ft=int(cruise.optimum_altitude_ft),
            strategy=climb_strategy,
        )
        climb = climb_profile.points
        landing = self.landing.calculate(
            landing_weight_lb,
            takeoff_inputs.environment,
            takeoff_inputs.runway,
            flaps="DOWN",
            planning_factor=takeoff_inputs.runway_factor,
        )
        fuel = self.fuel.plan(starting_fuel_lb, route_nm, climb, cruise, bingo_lb, joker_margin_lb)
        return MissionCard(
            takeoff=takeoff,
            climb=climb,
            cruise=cruise,
            landing=landing,
            fuel=fuel,
            metadata={
                "route_nm": route_nm,
                "drag_index": drag_index,
                "isa_delta_c": isa_delta_c,
                "model": "F-14 EFB",
                "climb_strategy": climb_profile.strategy,
                "climb_profile_label": climb_profile.label,
                "climb_time_to_cruise_min": climb_profile.time_min,
                "climb_fuel_to_cruise_lb": climb_profile.fuel_burn_lb,
                "climb_distance_to_cruise_nm": climb_profile.distance_nm,
            },
        )
