from __future__ import annotations

import math
from pathlib import Path

from .aero import F14AeroModel
from .atmosphere import atmosphere, ias_to_tas_kt, isa_temperature_c, mach_from_tas
from .engine import F110Deck
from .provenance import Method, Provenance, combine
from .types import ClimbPoint, ClimbProfile


KG_M3_TO_SLUG_FT3 = 0.00194032033
KT_TO_FPS = 1.68780986
CLIMB_STRATEGY_LABELS = {
    "MOST_EFFICIENT": "Most Efficient",
    "MINIMUM_TIME": "Minimum Time (MIL)",
}


class ClimbModel:
    def __init__(self, data_dir: Path | str | None = None):
        self.engine = F110Deck(data_dir)
        self.aero = F14AeroModel()

    def point(
        self,
        weight_lb: float,
        altitude_ft: float,
        ias_kt: float,
        rpm_pct: float = 100.0,
        isa_delta_c: float = 0.0,
        drag_index: float = 0.0,
        engines: int = 2,
    ) -> ClimbPoint:
        oat = isa_temperature_c(altitude_ft) + isa_delta_c
        atm = atmosphere(altitude_ft, oat)
        tas_kt = ias_to_tas_kt(ias_kt, atm["sigma"])
        mach = mach_from_tas(tas_kt, atm["speed_of_sound_kt"])
        eng = self.engine.total(
            altitude_ft, mach, mode="MIL", rpm_pct=rpm_pct, oat_c=oat, engines=engines
        )
        rho_slug = atm["rho_kg_m3"] * KG_M3_TO_SLUG_FT3
        aero = self.aero.point(
            weight_lb,
            rho_slug,
            tas_kt * KT_TO_FPS,
            mach,
            config="CLEAN",
            load_factor=1.0,
            drag_index=drag_index,
        )
        excess = eng.thrust_lbf_per_engine - aero.drag_lbf
        gradient = max(-3000.0, excess / max(1.0, weight_lb) * 6076.12)
        roc = gradient * tas_kt / 60.0
        prov = Provenance(
            Method.ESTIMATED,
            "F110 deck + low-order excess-thrust climb model",
            f"{engines} engine(s), {ias_kt:.0f} KIAS, {rpm_pct:.0f}% RPM, DI {drag_index:.0f}",
            "Medium for trend comparison; not a released F-14B climb chart",
        )
        return ClimbPoint(
            altitude_ft=round(altitude_ft),
            ias_kt=round(ias_kt, 1),
            tas_kt=round(tas_kt, 1),
            rpm_pct=round(rpm_pct, 1),
            roc_fpm=round(roc),
            gradient_ft_nm=round(gradient),
            fuel_flow_pph_total=round(eng.fuel_flow_pph_per_engine),
            provenance=prov,
        )

    @staticmethod
    def _strategy_key(strategy: str) -> str:
        key = str(strategy).strip().upper().replace("-", "_").replace(" ", "_")
        aliases = {
            "EFFICIENT": "MOST_EFFICIENT",
            "ECONOMY": "MOST_EFFICIENT",
            "MIN_TIME": "MINIMUM_TIME",
            "FASTEST": "MINIMUM_TIME",
        }
        key = aliases.get(key, key)
        if key not in CLIMB_STRATEGY_LABELS:
            raise ValueError(
                "Climb strategy must be MOST_EFFICIENT or MINIMUM_TIME."
            )
        return key

    def recommend_schedule(
        self,
        weight_lb: float,
        isa_delta_c: float = 0.0,
        drag_index: float = 0.0,
        target_gradient_ft_nm: float = 300.0,
        start_alt_ft: int = 1000,
        end_alt_ft: int = 10000,
        strategy: str = "MOST_EFFICIENT",
    ) -> list[ClimbPoint]:
        strategy_key = self._strategy_key(strategy)
        if start_alt_ft <= 0 or end_alt_ft < start_alt_ft:
            raise ValueError("Climb altitude range must start above zero and end at or above the start altitude.")

        schedule: list[ClimbPoint] = []
        speeds = list(range(190, 251, 10))
        for altitude in range(start_alt_ft, end_alt_ft + 1, 1000):
            chosen = None
            candidates: list[ClimbPoint] = []
            if strategy_key == "MOST_EFFICIENT":
                for rpm in range(85, 101):
                    rpm_candidates = [
                        self.point(
                            weight_lb,
                            altitude,
                            ias,
                            rpm,
                            isa_delta_c,
                            drag_index,
                        )
                        for ias in speeds
                    ]
                    candidates.extend(rpm_candidates)
                    feasible = [
                        p
                        for p in rpm_candidates
                        if p.gradient_ft_nm >= target_gradient_ft_nm and p.roc_fpm > 0
                    ]
                    if feasible:
                        chosen = min(
                            feasible,
                            key=lambda p: (
                                p.fuel_flow_pph_total / max(1.0, p.roc_fpm),
                                p.ias_kt,
                            ),
                        )
                        break
            else:
                candidates = [
                    self.point(
                        weight_lb,
                        altitude,
                        ias,
                        100,
                        isa_delta_c,
                        drag_index,
                    )
                    for ias in speeds
                ]
                feasible = [
                    p
                    for p in candidates
                    if p.gradient_ft_nm >= target_gradient_ft_nm and p.roc_fpm > 0
                ]
                if feasible:
                    chosen = max(
                        feasible,
                        key=lambda p: (
                            p.roc_fpm,
                            p.gradient_ft_nm,
                            -p.fuel_flow_pph_total,
                        ),
                    )

            if chosen is None:
                if not candidates:
                    candidates = [
                        self.point(
                            weight_lb,
                            altitude,
                            ias,
                            100,
                            isa_delta_c,
                            drag_index,
                        )
                        for ias in speeds
                    ]
                chosen = max(
                    candidates,
                    key=lambda p: p.roc_fpm,
                )
            schedule.append(chosen)
        return schedule

    def profile(
        self,
        weight_lb: float,
        isa_delta_c: float = 0.0,
        drag_index: float = 0.0,
        target_gradient_ft_nm: float = 300.0,
        start_alt_ft: int = 1000,
        end_alt_ft: int = 10000,
        strategy: str = "MOST_EFFICIENT",
    ) -> ClimbProfile:
        strategy_key = self._strategy_key(strategy)
        points = self.recommend_schedule(
            weight_lb,
            isa_delta_c,
            drag_index,
            target_gradient_ft_nm,
            start_alt_ft,
            end_alt_ft,
            strategy_key,
        )

        previous_altitude = 0.0
        total_minutes = 0.0
        fuel_burn_lb = 0.0
        altitude_gain_ft = 0.0
        for point in points:
            segment_ft = max(0.0, point.altitude_ft - previous_altitude)
            previous_altitude = point.altitude_ft
            segment_minutes = segment_ft / max(100.0, point.roc_fpm)
            total_minutes += segment_minutes
            fuel_burn_lb += point.fuel_flow_pph_total * segment_minutes / 60.0
            altitude_gain_ft += segment_ft

        unmet_segments = sum(
            point.gradient_ft_nm < target_gradient_ft_nm for point in points
        )
        if strategy_key == "MOST_EFFICIENT":
            strategy_note = (
                "Uses the lowest dry RPM that meets the gradient gate, then minimizes modeled fuel burned per foot at that power."
            )
            detail = "lowest feasible 85-100% dry RPM, then 190-250 KIAS fuel-per-foot search"
        else:
            strategy_note = (
                "Uses 100% dry MIL and selects the modeled maximum rate of climb at each altitude."
            )
            detail = "100% dry MIL and 190-250 KIAS search"

        notes = [
            strategy_note,
            "The 250 KIAS ceiling remains active through 10,000 ft.",
        ]
        if unmet_segments:
            notes.append(
                f"{unmet_segments} altitude segment(s) cannot meet the selected gradient gate in the current model."
            )

        provenance = Provenance(
            Method.ESTIMATED,
            "Named climb-profile optimizer",
            f"{CLIMB_STRATEGY_LABELS[strategy_key]}; {detail}; DI {drag_index:.0f}; ISA deviation {isa_delta_c:+.0f} C",
            "Medium for relative strategy comparison; not a released F-14B climb chart",
        )
        return ClimbProfile(
            strategy=strategy_key,
            label=CLIMB_STRATEGY_LABELS[strategy_key],
            points=points,
            time_min=round(total_minutes, 2),
            fuel_burn_lb=round(fuel_burn_lb),
            altitude_gain_ft=round(altitude_gain_ft),
            target_gradient_ft_nm=round(target_gradient_ft_nm),
            unmet_segments=unmet_segments,
            provenance=provenance,
            notes=notes,
        )

    def profiles(
        self,
        weight_lb: float,
        isa_delta_c: float = 0.0,
        drag_index: float = 0.0,
        target_gradient_ft_nm: float = 300.0,
        start_alt_ft: int = 1000,
        end_alt_ft: int = 10000,
    ) -> dict[str, ClimbProfile]:
        return {
            strategy: self.profile(
                weight_lb,
                isa_delta_c,
                drag_index,
                target_gradient_ft_nm,
                start_alt_ft,
                end_alt_ft,
                strategy,
            )
            for strategy in CLIMB_STRATEGY_LABELS
        }
