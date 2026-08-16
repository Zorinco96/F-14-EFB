from __future__ import annotations

from .provenance import Method, Provenance
from .types import ClimbPoint, CruiseResult, FuelPlan


USABLE_FUEL_ROUGH_LB = 20000.0


class FuelModel:
    def plan(
        self,
        starting_fuel_lb: float,
        route_nm: float,
        climb_schedule: list[ClimbPoint],
        cruise: CruiseResult,
        bingo_lb: float = 4000.0,
        joker_margin_lb: float = 2000.0,
    ) -> FuelPlan:
        warnings: list[str] = []
        if starting_fuel_lb > USABLE_FUEL_ROUGH_LB + 500:
            warnings.append("Starting fuel exceeds the roughly 20,000 lb usable-fuel figure documented by Heatblur.")
        taxi_takeoff = 400.0
        climb_burn = 0.0
        previous_altitude = 0.0
        for p in climb_schedule:
            if p.roc_fpm <= 100:
                continue
            segment_ft = max(0.0, p.altitude_ft - previous_altitude)
            previous_altitude = p.altitude_ft
            minutes = segment_ft / p.roc_fpm
            climb_burn += p.fuel_flow_pph_total / 60.0 * minutes
        if climb_schedule and cruise.optimum_altitude_ft > climb_schedule[-1].altitude_ft:
            extra_alt = cruise.optimum_altitude_ft - climb_schedule[-1].altitude_ft
            extra_minutes = extra_alt / 1500.0
            climb_burn += max(cruise.fuel_flow_pph_total * 1.75, 14000.0) / 60.0 * extra_minutes
        cruise_hours = max(0.0, route_nm) / max(100.0, cruise.tas_kt)
        cruise_burn = cruise.fuel_flow_pph_total * cruise_hours
        descent_approach = 550.0
        mission_burn = taxi_takeoff + climb_burn + cruise_burn + descent_approach
        landing = starting_fuel_lb - mission_burn
        joker = bingo_lb + joker_margin_lb
        if landing < bingo_lb:
            warnings.append(f"Estimated landing fuel is {bingo_lb - landing:.0f} lb below BINGO.")
        elif landing < joker:
            warnings.append("Estimated landing fuel is below JOKER but above BINGO.")
        return FuelPlan(
            starting_fuel_lb=round(starting_fuel_lb),
            taxi_takeoff_lb=round(taxi_takeoff),
            climb_lb=round(climb_burn),
            cruise_lb=round(cruise_burn),
            descent_approach_lb=round(descent_approach),
            mission_burn_lb=round(mission_burn),
            landing_fuel_lb=round(landing),
            joker_lb=round(joker),
            bingo_lb=round(bingo_lb),
            provenance=Provenance(
                Method.ESTIMATED,
                "Mission fuel planning model",
                "Phase-based taxi/takeoff, conservative climb allowance, modeled cruise, fixed descent/approach allowance",
                "Low-medium; intentionally biased toward fuel margin for DCS planning",
            ),
            warnings=warnings,
        )
