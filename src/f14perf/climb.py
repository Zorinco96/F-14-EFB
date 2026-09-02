from __future__ import annotations

import math
from pathlib import Path

from .atmosphere import (
    atmosphere,
    cas_to_mach,
    isa_temperature_c,
    mach_to_cas_kt,
)
from .engine import F110Deck
from .provenance import Method, Provenance
from .types import ClimbPoint, ClimbProfile


CLIMB_STRATEGY_LABELS = {
    "MOST_EFFICIENT": "Conservative dry planning",
    "MINIMUM_TIME": "MIL climb planning",
}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class ClimbModel:
    """Conservative DCS mission-planning climb schedule.

    The previous optimizer treated a low-order drag polar and a legacy engine
    deck as a released F-14B climb chart. It generated implausible rates above
    20,000 fpm and understated fuel. This model intentionally does not predict
    maximum aircraft capability. It supplies guarded planning rates and uses
    the engine deck only for a per-engine fuel-flow estimate.
    """

    def __init__(self, data_dir: Path | str | None = None):
        self.engine = F110Deck(data_dir)

    @staticmethod
    def _strategy_key(strategy: str) -> str:
        key = str(strategy).strip().upper().replace("-", "_").replace(" ", "_")
        aliases = {
            "EFFICIENT": "MOST_EFFICIENT",
            "ECONOMY": "MOST_EFFICIENT",
            "MIN_TIME": "MINIMUM_TIME",
            "FASTEST": "MINIMUM_TIME",
            "MIL": "MINIMUM_TIME",
        }
        key = aliases.get(key, key)
        if key not in CLIMB_STRATEGY_LABELS:
            raise ValueError("Climb strategy must be MOST_EFFICIENT or MINIMUM_TIME.")
        return key

    @staticmethod
    def _planning_rate(
        weight_lb: float,
        altitude_ft: float,
        isa_delta_c: float,
        drag_index: float,
        strategy: str,
    ) -> float:
        altitude_kft = max(0.0, altitude_ft / 1000.0)
        if strategy == "MINIMUM_TIME":
            base_rate = 3_200.0 - 80.0 * altitude_kft
        else:
            base_rate = 2_450.0 - 60.0 * altitude_kft

        weight_factor = _clamp((65_000.0 / max(45_000.0, weight_lb)) ** 0.70, 0.82, 1.12)
        hot_day_factor = _clamp(1.0 - 0.006 * max(0.0, isa_delta_c), 0.82, 1.0)
        store_factor = _clamp(1.0 - 0.010 * max(0.0, drag_index), 0.75, 1.0)
        return _clamp(base_rate * weight_factor * hot_day_factor * store_factor, 800.0, 3_500.0)

    def point(
        self,
        weight_lb: float,
        altitude_ft: float,
        ias_kt: float,
        rpm_pct: float = 100.0,
        isa_delta_c: float = 0.0,
        drag_index: float = 0.0,
        engines: int = 2,
        planning_roc_fpm: float | None = None,
    ) -> ClimbPoint:
        if engines != 2:
            raise ValueError("The mission climb schedule is defined for two engines operating.")
        oat = isa_temperature_c(altitude_ft) + isa_delta_c
        atm = atmosphere(altitude_ft, oat)
        mach = cas_to_mach(ias_kt, atm["pressure_pa"])
        tas_kt = mach * atm["speed_of_sound_kt"]
        engine = self.engine.point(
            altitude_ft,
            mach,
            mode="MIL",
            rpm_pct=rpm_pct,
            oat_c=oat,
        )
        strategy = "MINIMUM_TIME" if rpm_pct >= 99.5 else "MOST_EFFICIENT"
        roc = planning_roc_fpm or self._planning_rate(
            weight_lb, altitude_ft, isa_delta_c, drag_index, strategy
        )
        gradient = roc * 60.0 / max(1.0, tas_kt)
        prov = Provenance(
            Method.ESTIMATED,
            "Conservative DCS climb-planning schedule",
            f"{ias_kt:.0f} KIAS, {rpm_pct:.0f}% RPM; weight, temperature, and store allowances applied",
            "Guarded planning allowance, not predicted maximum climb capability",
        )
        return ClimbPoint(
            altitude_ft=round(altitude_ft),
            ias_kt=round(ias_kt),
            tas_kt=round(tas_kt),
            rpm_pct=round(rpm_pct),
            roc_fpm=round(roc / 100.0) * 100,
            gradient_ft_nm=round(gradient / 10.0) * 10,
            fuel_flow_pph_per_engine=round(engine.fuel_flow_pph_per_engine / 100.0) * 100,
            provenance=prov,
        )

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

        rpm = 100.0 if strategy_key == "MINIMUM_TIME" else 95.0
        schedule: list[ClimbPoint] = []
        for altitude in range(start_alt_ft, end_alt_ft + 1, 1000):
            oat = isa_temperature_c(altitude) + isa_delta_c
            atm = atmosphere(altitude, oat)
            mach_limited_ias = mach_to_cas_kt(0.72, atm["pressure_pa"])
            if altitude <= 10_000:
                ias = 250.0
            else:
                ias = round(min(300.0, mach_limited_ias) / 5.0) * 5.0
            rate = self._planning_rate(
                weight_lb, altitude, isa_delta_c, drag_index, strategy_key
            )
            schedule.append(
                self.point(
                    weight_lb,
                    altitude,
                    ias,
                    rpm,
                    isa_delta_c,
                    drag_index,
                    planning_roc_fpm=rate,
                )
            )
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

        previous_altitude = max(0.0, start_alt_ft - 1000.0)
        total_minutes = 0.0
        fuel_burn_lb = 0.0
        distance_nm = 0.0
        altitude_gain_ft = 0.0
        for point in points:
            segment_ft = max(0.0, point.altitude_ft - previous_altitude)
            previous_altitude = point.altitude_ft
            segment_minutes = segment_ft / max(100.0, point.roc_fpm)
            total_minutes += segment_minutes
            fuel_burn_lb += point.fuel_flow_pph_total * segment_minutes / 60.0
            distance_nm += point.tas_kt * segment_minutes / 60.0
            altitude_gain_ft += segment_ft

        unmet_segments = sum(
            p.altitude_ft <= 10_000 and p.gradient_ft_nm < target_gradient_ft_nm
            for p in points
        )
        rpm_label = "MIL" if strategy_key == "MINIMUM_TIME" else "95% dry"
        notes = [
            "NATOPS Figure 14-1 gives 6.0 units AOA at sea level increasing to 9.5 at combat ceiling for a MIL climb only as an alternate cue following an airspeed-indicator failure.",
            f"The internal {rpm_label} time/fuel integration uses 250 KIAS through 10,000 ft, then 300 KIAS to the Mach 0.72 crossover; this is an engineering assumption, not a published pilot cue.",
            "Rate, time, distance, and fuel are conservative mission-planning allowances. They are not NATOPS chart outputs or maximum-rate predictions.",
            "Displayed fuel flow is PPH per engine; profile fuel burn is the two-engine aircraft total.",
            "Elapsed time is rounded up to a whole minute, distance to 5 NM, and fuel to 500 lb to avoid false precision.",
        ]
        if unmet_segments:
            notes.append(f"{unmet_segments} segment(s) through 10,000 ft fall below the selected planning gradient.")

        provenance = Provenance(
            Method.ESTIMATED,
            "Conservative DCS climb profile",
            f"{CLIMB_STRATEGY_LABELS[strategy_key]}; guarded rate schedule; DI allowance {drag_index:.0f}; ISA {isa_delta_c:+.0f} C",
            "Low-medium absolute accuracy; biased toward time and fuel margin",
        )
        return ClimbProfile(
            strategy=strategy_key,
            label=CLIMB_STRATEGY_LABELS[strategy_key],
            points=points,
            time_min=math.ceil(total_minutes),
            fuel_burn_lb=math.ceil(fuel_burn_lb / 500.0) * 500,
            distance_nm=math.ceil(distance_nm / 5.0) * 5.0,
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
