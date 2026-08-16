from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from .atmosphere import atmosphere, mach_from_tas, pressure_altitude_ft, ias_to_tas_kt
from .data import read_csv, require_columns
from .engine import F110Deck
from .interpolate import regular_grid_interpolate
from .provenance import Method, Provenance, combine, worst_method
from .types import TakeoffInputs, TakeoffResult
from .weather import wind_components


CONFIG_TABLE_CODE = {"UP": 0, "MANEUVER": 20, "FULL": 40}
AUTO_ORDER = ("UP", "MANEUVER", "FULL")
RPM_FLOOR = {"UP": 85, "MANEUVER": 90, "FULL": 96}
MANEUVER_ANCHOR = {
    "weight_lb": 65000.0,
    "vs_kt": 122.0,
    "v1_ref_kt": 137.0,
    "vr_kt": 146.0,
    "v2_kt": 159.0,
    "asd_ft": 2583.0,
    "agd_ft": 2456.0,
}
CLIMB_ANCHOR_FT_NM = {"UP": 430.0, "MANEUVER": 455.0, "FULL": 410.0}
TAKEOFF_TRIM_SCHEDULE_ANU = {"UP": 3.0, "MANEUVER": 6.0, "FULL": 0.0}
MANEUVER_TRIM_TEST_BAND_ANU = (5.0, 7.0)


class TakeoffModel:
    REQUIRED = {
        "model", "flap_deg", "thrust", "gw_lbs", "press_alt_ft", "oat_c",
        "vs_kt", "v1_kt", "vr_kt", "v2_kt", "asd_ft", "agd_ft", "note",
    }

    def __init__(self, data_dir: Path | str | None = None):
        self.data_dir = data_dir
        self.df = read_csv("f14_perf.csv", data_dir)
        self.df.columns = [str(c).strip().lower() for c in self.df.columns]
        require_columns(self.df, self.REQUIRED, "f14_perf.csv")
        self.df["model"] = self.df["model"].astype(str).str.upper()
        self.df["thrust"] = self.df["thrust"].astype(str).str.upper()
        self.vspeeds = read_csv("vspeeds.csv", data_dir)
        self.vspeeds.columns = [str(c).strip().lower() for c in self.vspeeds.columns]
        require_columns(self.vspeeds, {"weight", "v2", "vfs"}, "vspeeds.csv")
        self.engine = F110Deck(data_dir)

    def _mil_table(self, flaps: str, weight_lb: float, pa_ft: float, oat_c: float) -> tuple[dict, Provenance]:
        flap_code = CONFIG_TABLE_CODE[flaps]
        sub = self.df[
            (self.df["model"] == "F-14B")
            & (self.df["thrust"] == "MILITARY")
            & (self.df["flap_deg"].astype(float) == float(flap_code))
        ]
        if sub.empty and flaps == "MANEUVER":
            return self._maneuver_calibrated(weight_lb, pa_ft, oat_c)
        if sub.empty:
            raise ValueError(f"No MIL takeoff table available for {flaps}")

        axes = {"gw_lbs": weight_lb, "press_alt_ft": pa_ft, "oat_c": oat_c}
        values = {}
        methods = []
        details = []
        for output in ("vs_kt", "v1_kt", "vr_kt", "v2_kt", "asd_ft", "agd_ft"):
            r = regular_grid_interpolate(sub, axes, output)
            values[output] = r.value
            methods.append(r.method)
            details.append(f"{output}:{r.method.value}")
        method = worst_method(methods)
        source_notes = sorted(set(sub["note"].dropna().astype(str)))
        prov = Provenance(
            method,
            "Legacy f14_perf.csv MIL grid",
            f"Flap table code {flap_code}; " + ", ".join(details) + f"; source labels={source_notes[:3]}",
            "Medium-high inside legacy grid; source transcription not independently re-digitized in v3",
        )
        return values, prov

    def _maneuver_calibrated(self, weight_lb: float, pa_ft: float, oat_c: float) -> tuple[dict, Provenance]:
        up_now, up_prov = self._mil_table("UP", weight_lb, pa_ft, oat_c)
        up_ref, _ = self._mil_table("UP", 65000.0, 0.0, 15.0)
        w_scale = math.sqrt(max(0.5, weight_lb / MANEUVER_ANCHOR["weight_lb"]))
        values = {
            "vs_kt": MANEUVER_ANCHOR["vs_kt"] * w_scale,
            "v1_kt": MANEUVER_ANCHOR["v1_ref_kt"] * w_scale,
            "vr_kt": MANEUVER_ANCHOR["vr_kt"] * w_scale,
            "v2_kt": MANEUVER_ANCHOR["v2_kt"] * w_scale,
            "asd_ft": MANEUVER_ANCHOR["asd_ft"] * (up_now["asd_ft"] / up_ref["asd_ft"]),
            "agd_ft": MANEUVER_ANCHOR["agd_ft"] * (up_now["agd_ft"] / up_ref["agd_ft"]),
        }
        prov = Provenance(
            Method.CALIBRATED if up_prov.method != Method.EXTRAPOLATED else Method.EXTRAPOLATED,
            "DCS maneuver-flap calibration + UP-grid environmental scaling",
            "65,000 lb SL/15 C anchor: Vr 146, ASD 2583 ft, takeoff distance 2456 ft",
            "Medium near calibration point; lower as weight/altitude/temperature depart the grid",
        )
        return values, prov

    def _takeoff_references(
        self,
        weight_lb: float,
        active_v2_kt: float,
    ) -> tuple[float, float, Provenance]:
        legacy_v2 = regular_grid_interpolate(
            self.vspeeds,
            {"weight": weight_lb},
            "v2",
        )
        legacy_vfs = regular_grid_interpolate(
            self.vspeeds,
            {"weight": weight_lb},
            "vfs",
        )
        vfs_spread_kt = legacy_vfs.value - legacy_v2.value
        if not 0.0 < vfs_spread_kt <= 40.0:
            raise ValueError(
                "Legacy Vfs-to-V2 spread must be greater than 0 and no more than 40 kt."
            )

        vfs_kt = active_v2_kt + vfs_spread_kt
        oei_climb_speed_kt = active_v2_kt + 15.0
        provenance = Provenance(
            Method.ESTIMATED,
            "Legacy Vfs spread and locked OEI takeoff policy",
            f"vspeeds.csv spread {vfs_spread_kt:.1f} kt; OEI target V2+15; "
            f"V2 lookup {legacy_v2.method.value}; Vfs lookup {legacy_vfs.method.value}",
            "Documented 000 trim procedure; Vfs and OEI performance remain subject to DCS validation",
        )
        return vfs_kt, oei_climb_speed_kt, provenance

    @staticmethod
    def _takeoff_trim_anu(flaps: str) -> float:
        """Return the explicit pre-roll trim schedule for the selected flap setting."""
        return TAKEOFF_TRIM_SCHEDULE_ANU[flaps]

    @staticmethod
    def _surface_slope_factors(headwind_kt: float, vr_kt: float, slope_pct: float, condition: str) -> tuple[float, float, list[str]]:
        warnings: list[str] = []
        wind_factor = ((max(50.0, vr_kt - headwind_kt)) / max(50.0, vr_kt)) ** 2
        wind_factor = max(0.65, min(1.80, wind_factor))
        tod_slope = max(0.80, 1.0 + 0.08 * slope_pct)
        stop_slope = max(0.80, 1.0 + 0.05 * max(0.0, -slope_pct))
        tod = wind_factor * tod_slope
        stop = wind_factor * stop_slope
        if condition.upper() == "WET":
            tod *= 1.05
            stop *= 1.25
            warnings.append("Wet-runway correction is an engineering estimate, not a released F-14B chart correction.")
        if headwind_kt < 0:
            warnings.append(f"Credited tailwind component {abs(headwind_kt):.1f} kt increases runway requirement.")
        return stop, tod, warnings

    @staticmethod
    def _credited_wind(
        headwind_kt: float,
        headwind_credit_pct: float,
        tailwind_penalty_pct: float,
    ) -> float:
        if not 0.0 <= headwind_credit_pct <= 100.0:
            raise ValueError("Headwind credit must be between 0 and 100 percent.")
        if not 100.0 <= tailwind_penalty_pct <= 200.0:
            raise ValueError("Tailwind penalty must be between 100 and 200 percent.")
        factor = headwind_credit_pct if headwind_kt >= 0.0 else tailwind_penalty_pct
        return headwind_kt * factor / 100.0

    def _reduced_thrust(self, base: dict, rpm_pct: float, pa_ft: float, oat_c: float, vr_kt: float) -> tuple[dict, Provenance]:
        atm = atmosphere(pa_ft, oat_c)
        tas = ias_to_tas_kt(vr_kt, atm["sigma"])
        mach = mach_from_tas(tas, atm["speed_of_sound_kt"])
        mil = self.engine.total(pa_ft, mach, mode="MIL", rpm_pct=100.0, oat_c=oat_c)
        selected = self.engine.total(pa_ft, mach, mode="MIL", rpm_pct=rpm_pct, oat_c=oat_c)
        ratio = max(0.20, selected.thrust_lbf_per_engine / max(1.0, mil.thrust_lbf_per_engine))
        out = dict(base)
        out["agd_ft"] *= ratio ** -1.18
        out["asd_ft"] *= 1.0 + 0.22 * (ratio ** -1.0 - 1.0)
        prov = Provenance(
            Method.ESTIMATED if rpm_pct < 99.9 else mil.provenance.method,
            "Reduced-thrust takeoff correction",
            f"Thrust ratio {ratio:.3f}; AGD exponent -1.18; ASD acceleration correction applied",
            "Medium at MIL; low-medium when materially derated",
        )
        return out, prov

    @staticmethod
    def _balanced_v1(v1_ref: float, vr: float, asd_ref: float, agd_ref: float) -> tuple[float, float, float]:
        low = max(90.0, 0.84 * vr)
        high = max(low, vr - 3.0)
        candidates = np.arange(low, high + 0.01, 0.5)
        best = None
        for v1 in candidates:
            asd = asd_ref * (v1 / max(1.0, v1_ref)) ** 2
            go_factor = max(0.72, min(1.35, 1.0 - 0.0070 * (v1 - v1_ref)))
            agd = agd_ref * go_factor
            metric = abs(asd - agd)
            if best is None or metric < best[0]:
                best = (metric, v1, asd, agd)
        assert best is not None
        return float(best[1]), float(best[2]), float(best[3])

    def _calibrated_climb(self, flaps: str, rpm_pct: float, weight_lb: float, pa_ft: float, oat_c: float, v2_kt: float) -> tuple[float, float, Provenance]:
        atm = atmosphere(pa_ft, oat_c)
        tas = ias_to_tas_kt(v2_kt, atm["sigma"])
        mach = mach_from_tas(tas, atm["speed_of_sound_kt"])
        mil = self.engine.total(pa_ft, mach, mode="MIL", rpm_pct=100.0, oat_c=oat_c)
        sel = self.engine.total(pa_ft, mach, mode="MIL", rpm_pct=rpm_pct, oat_c=oat_c)
        ratio = max(0.2, sel.thrust_lbf_per_engine / max(1.0, mil.thrust_lbf_per_engine))
        gradient = CLIMB_ANCHOR_FT_NM[flaps] * (65000.0 / weight_lb) * ratio ** 0.55 * atm["sigma"] ** 0.10
        oei = max(0.0, gradient * 0.48 - 35.0)
        prov = Provenance(
            Method.CALIBRATED,
            "DCS-calibrated initial climb model",
            f"{flaps} 65,000 lb MIL anchor {CLIMB_ANCHOR_FT_NM[flaps]:.0f} ft/NM; thrust/weight/density scaled",
            "Medium for AEO trend; low-medium for OEI advisory",
        )
        return gradient, oei, prov

    def calculate(self, inputs: TakeoffInputs, flaps: str, rpm_pct: float) -> TakeoffResult:
        flaps = flaps.upper()
        if flaps not in AUTO_ORDER:
            raise ValueError(f"Unsupported takeoff flap configuration: {flaps}")
        if not 40000 <= inputs.weight_lb <= 76000:
            raise ValueError("F-14B takeoff weight must be between 40,000 and 76,000 lb for this model.")
        if not 70 <= rpm_pct <= 100:
            raise ValueError("Takeoff RPM must be between 70 and 100 percent.")
        loadout_label = inputs.takeoff_loadout.strip() or "Clean"

        field_elev = inputs.runway.elevation_ft
        if field_elev is None:
            field_elev = inputs.environment.field_elevation_ft
        pa = pressure_altitude_ft(field_elev, inputs.environment.qnh_inhg)
        base, table_prov = self._mil_table(flaps, inputs.weight_lb, pa, inputs.environment.oat_c)
        corrected, thrust_prov = self._reduced_thrust(base, rpm_pct, pa, inputs.environment.oat_c, base["vr_kt"])
        vfs_kt, oei_climb_speed_kt, takeoff_reference_prov = self._takeoff_references(
            inputs.weight_lb,
            corrected["v2_kt"],
        )
        takeoff_trim_anu = self._takeoff_trim_anu(flaps)

        raw_headwind, _ = wind_components(
            inputs.environment.wind_dir_deg,
            inputs.environment.wind_speed_kt,
            inputs.runway.heading_deg,
        )
        credited_headwind = self._credited_wind(
            raw_headwind,
            inputs.headwind_credit_pct,
            inputs.tailwind_penalty_pct,
        )
        stop_factor, go_factor, warnings = self._surface_slope_factors(
            credited_headwind,
            corrected["vr_kt"],
            inputs.runway.slope_pct,
            inputs.runway.condition,
        )
        asd_before_v1 = corrected["asd_ft"] * stop_factor
        agd_before_v1 = corrected["agd_ft"] * go_factor
        v1, asd, agd = self._balanced_v1(
            corrected["v1_kt"], corrected["vr_kt"], asd_before_v1, agd_before_v1
        )
        v1_prov = Provenance(
            Method.ESTIMATED,
            "Balanced-field V1 sweep",
            "0.5-kt numerical sweep using kinetic-energy reject scaling and estimated OEI go-distance sensitivity",
            "Low-medium until controlled DCS engine-cut sweeps are added",
        )
        climb, climb_oei, climb_prov = self._calibrated_climb(
            flaps, rpm_pct, inputs.weight_lb, pa, inputs.environment.oat_c, corrected["v2_kt"]
        )
        eig_reference = self.engine.takeoff_eig_reference(
            rpm_pct,
            pressure_altitude_ft=pa,
            oat_c=inputs.environment.oat_c,
        )
        thrust_setting = (
            "MILITARY" if rpm_pct >= 99.5 else f"REDUCED ({rpm_pct:.0f}% RPM)"
        )

        factored_asd = asd * inputs.runway_factor
        factored_agd = agd * inputs.runway_factor
        asda_margin = inputs.runway.asda_ft - factored_asd
        toda_margin = inputs.runway.toda_ft - factored_agd
        runway_ok = asda_margin >= 0 and toda_margin >= 0
        climb_ok = climb >= inputs.climb_target_ft_nm
        feasible = runway_ok and climb_ok

        external_store_drag_unmodeled = loadout_label.casefold() != "clean"
        hot_high_reduced_thrust = (
            pa >= 2000.0
            and inputs.environment.oat_c >= 35.0
            and rpm_pct < 99.5
        )
        takeoff_data_valid = not (
            external_store_drag_unmodeled or hot_high_reduced_thrust
        )

        if external_store_drag_unmodeled:
            warnings.append(
                f"External-store takeoff drag is not modeled for {loadout_label}. "
                "Distances, margins, climb, and any GO indication are unvalidated."
            )
        if hot_high_reduced_thrust:
            warnings.append(
                "Hot/high reduced-thrust runway performance is unvalidated. Fuel-flow guidance "
                "uses the limited Henderson observations within the tested 95-98% RPM envelope, "
                "but the thrust and runway-distance correction is not calibrated."
            )

        if rpm_pct < RPM_FLOOR[flaps]:
            warnings.append(f"{flaps} selected below AUTO policy floor of {RPM_FLOOR[flaps]}% RPM.")
        if asda_margin < 0:
            warnings.append(f"Factored accelerate-stop distance exceeds ASDA by {abs(asda_margin):.0f} ft.")
        if toda_margin < 0:
            warnings.append(f"Factored accelerate-go distance exceeds TODA by {abs(toda_margin):.0f} ft.")
        if not climb_ok:
            warnings.append(
                f"AEO initial climb gradient {climb:.0f} ft/NM is below the {inputs.climb_target_ft_nm:.0f} ft/NM planning gate."
            )
        if pa < -1000 or pa > 10000:
            warnings.append("Pressure altitude is outside the primary legacy takeoff grid; extrapolation risk is elevated.")
        if inputs.environment.oat_c < -10 or inputs.environment.oat_c > 50:
            warnings.append("Temperature is near/outside the primary legacy takeoff grid; inspect provenance carefully.")

        prov = combine(
            table_prov,
            thrust_prov,
            v1_prov,
            climb_prov,
            eig_reference.provenance,
            takeoff_reference_prov,
            source="Takeoff solution",
        )
        return TakeoffResult(
            feasible=feasible,
            flaps=flaps,
            rpm_pct=round(rpm_pct, 1),
            v1_kt=round(v1),
            v1_reference_kt=round(corrected["v1_kt"]),
            vr_kt=round(corrected["vr_kt"]),
            v2_kt=round(corrected["v2_kt"]),
            vfs_kt=round(vfs_kt),
            vs_kt=round(corrected["vs_kt"]),
            asd_ft=round(asd),
            agd_ft=round(agd),
            factored_asd_ft=round(factored_asd),
            factored_agd_ft=round(factored_agd),
            asda_margin_ft=round(asda_margin),
            toda_margin_ft=round(toda_margin),
            climb_gradient_ft_nm=round(climb),
            climb_gradient_oei_ft_nm=round(climb_oei),
            pressure_altitude_ft=round(pa),
            headwind_kt=round(raw_headwind, 1),
            credited_headwind_kt=round(credited_headwind, 1),
            thrust_setting=thrust_setting,
            eig_reference_rpm_pct=round(eig_reference.rpm_pct, 1),
            fuel_flow_pph_per_engine=round(eig_reference.fuel_flow_pph_per_engine),
            fuel_flow_pph_total=round(eig_reference.fuel_flow_pph_per_engine * 2.0),
            stabilizer_trim_anu=takeoff_trim_anu,
            stabilizer_trim_band_anu=(
                MANEUVER_TRIM_TEST_BAND_ANU if flaps == "MANEUVER" else None
            ),
            oei_climb_speed_kt=round(oei_climb_speed_kt),
            stabilizer_trim_note=(
                f"Set pitch trim {takeoff_trim_anu:.1f} ANU before commencing the takeoff roll. "
                + (
                    "The 6.0 ANU MANEUVER setting is provisional and the displayed 5.0 to 7.0 ANU range "
                    "is a trial range, not an accepted band. It targets an easy rotation at V2 without excessive backpressure. "
                    if flaps == "MANEUVER"
                    else "This provisional setting targets an easy rotation at V2 without excessive backpressure. "
                )
                +
                "For an engine failure after rotation, establish gear up, fly V2+15, "
                "and use MILITARY thrust on the operating engine. Trim as required after liftoff."
            ),
            takeoff_loadout=loadout_label,
            takeoff_data_valid=takeoff_data_valid,
            provenance=prov,
            warnings=warnings,
            notes=[
                f"Runway planning factor: {inputs.runway_factor:.2f}.",
                f"Wind policy: {inputs.headwind_credit_pct:.0f}% headwind credit / "
                f"{inputs.tailwind_penalty_pct:.0f}% tailwind penalty.",
                f"Fuel-flow guidance is per engine and advisory. Source: {eig_reference.provenance.source}.",
                "AUTO never selects afterburner for takeoff.",
                "OEI climb is advisory; the locked AUTO gate is AEO climb gradient.",
                "Pitch trim does not command airspeed; the pilot must control pitch to maintain the OEI V2+15 target.",
                "Current trim values are provisional. The latest 62,000 lb two-tank/two-AIM-9 tests found 5.0 ANU UP slightly heavy and 6.5 ANU MANEUVER heavy.",
                "FULL uses the legacy table's flap_deg=40 code while the cockpit configuration is displayed as FULL.",
            ],
        )


class AutoTakeoffSelector:
    def __init__(self, data_dir: Path | str | None = None):
        self.model = TakeoffModel(data_dir)

    @staticmethod
    def _penalty(result: TakeoffResult, target: float) -> float:
        return (
            max(0.0, -result.asda_margin_ft)
            + max(0.0, -result.toda_margin_ft)
            + max(0.0, target - result.climb_gradient_ft_nm) * 20.0
        )

    def select(self, inputs: TakeoffInputs) -> TakeoffResult:
        requested = inputs.flaps.upper()
        if requested != "AUTO" and requested not in AUTO_ORDER:
            raise ValueError("Flaps must be AUTO, UP, MANEUVER, or FULL.")

        if inputs.thrust.upper() == "MANUAL" or inputs.rpm_pct is not None:
            flaps = "UP" if requested == "AUTO" else requested
            rpm = 100.0 if inputs.rpm_pct is None else float(inputs.rpm_pct)
            return self.model.calculate(inputs, flaps, rpm)

        configurations = AUTO_ORDER if requested == "AUTO" else (requested,)
        all_results: list[TakeoffResult] = []
        for flaps in configurations:
            for rpm in range(RPM_FLOOR[flaps], 101):
                result = self.model.calculate(inputs, flaps, float(rpm))
                all_results.append(result)
                if result.feasible:
                    result.notes.insert(0, "AUTO selected the first feasible configuration by flap priority and minimum RPM.")
                    return result

        best = min(all_results, key=lambda r: self._penalty(r, inputs.climb_target_ft_nm))
        best.warnings.insert(0, "No AUTO configuration satisfies both runway and AEO climb planning criteria.")
        return best
