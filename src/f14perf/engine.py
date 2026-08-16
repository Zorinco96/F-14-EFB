from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .data import read_csv, require_columns
from .interpolate import regular_grid_interpolate
from .provenance import Method, Provenance, combine


@dataclass(frozen=True)
class EnginePoint:
    thrust_lbf_per_engine: float
    fuel_flow_pph_per_engine: float
    rpm_pct: float
    provenance: Provenance


class F110Deck:
    """F110-GE-400 performance layer backed by the repository engine deck.

    The legacy CSV is treated as a simulation model, not as a released NATOPS
    engine deck. Interpolation is direct where possible. Temperature and reduced
    RPM corrections are explicit estimates.
    """

    REQUIRED = {"altitude_ft", "mach", "thrust_type", "thrust_lbf", "ff_pph"}
    TAKEOFF_FF_REQUIRED = {"rpm_pct", "ff_pph"}
    TAKEOFF_FF_ENV_REQUIRED = {
        "pressure_altitude_ft",
        "oat_c",
        "rpm_pct",
        "ff_pph_per_engine",
        "n_runs",
        "source_note",
    }

    def __init__(self, data_dir: Path | str | None = None):
        self.df = read_csv("F110_engine.csv", data_dir)
        self.df.columns = [str(c).strip().lower() for c in self.df.columns]
        require_columns(self.df, self.REQUIRED, "F110_engine.csv")
        self.df["thrust_type"] = self.df["thrust_type"].astype(str).str.upper()
        self.takeoff_ff = read_csv("f110_ff_to_rpm_knots.csv", data_dir)
        self.takeoff_ff.columns = [str(c).strip().lower() for c in self.takeoff_ff.columns]
        require_columns(
            self.takeoff_ff,
            self.TAKEOFF_FF_REQUIRED,
            "f110_ff_to_rpm_knots.csv",
        )
        self.takeoff_ff_environment = read_csv(
            "f110_takeoff_ff_environment.csv",
            data_dir,
        )
        self.takeoff_ff_environment.columns = [
            str(c).strip().lower() for c in self.takeoff_ff_environment.columns
        ]
        require_columns(
            self.takeoff_ff_environment,
            self.TAKEOFF_FF_ENV_REQUIRED,
            "f110_takeoff_ff_environment.csv",
        )

    def _base(self, altitude_ft: float, mach: float, mode: str) -> EnginePoint:
        mode = mode.upper()
        sub = self.df[self.df["thrust_type"] == mode]
        if sub.empty:
            raise ValueError(f"No F110 data for mode {mode}")
        thrust = regular_grid_interpolate(
            sub, {"altitude_ft": altitude_ft, "mach": mach}, "thrust_lbf"
        )
        ff = regular_grid_interpolate(
            sub, {"altitude_ft": altitude_ft, "mach": mach}, "ff_pph"
        )
        method = thrust.method if thrust.method == ff.method else Method.ESTIMATED
        prov = Provenance(
            method,
            "Legacy repository F110_engine.csv",
            f"{mode} altitude/Mach lookup; {thrust.detail}",
            "Medium; simulation-oriented legacy deck",
        )
        return EnginePoint(thrust.value, ff.value, 100.0 if mode != "IDLE" else 70.0, prov)

    def point(
        self,
        altitude_ft: float,
        mach: float,
        mode: str = "MIL",
        rpm_pct: float = 100.0,
        oat_c: float | None = None,
    ) -> EnginePoint:
        mode = mode.upper()
        if mode == "AB":
            base = self._base(altitude_ft, mach, "AB")
            return EnginePoint(base.thrust_lbf_per_engine, base.fuel_flow_pph_per_engine, 100.0, base.provenance)
        if mode == "IDLE":
            return self._base(altitude_ft, mach, "IDLE")
        if mode not in {"MIL", "DRY", "REDUCED"}:
            raise ValueError(f"Unsupported F110 mode: {mode}")

        rpm = max(70.0, min(100.0, float(rpm_pct)))
        mil = self._base(altitude_ft, mach, "MIL")
        idle = self._base(altitude_ft, mach, "IDLE")
        x = max(0.0, min(1.0, (rpm - 70.0) / 30.0))
        dry_fraction = x ** 1.75
        thrust = idle.thrust_lbf_per_engine + dry_fraction * (
            mil.thrust_lbf_per_engine - idle.thrust_lbf_per_engine
        )
        ff_fraction = x ** 1.25
        ff = idle.fuel_flow_pph_per_engine + ff_fraction * (
            mil.fuel_flow_pph_per_engine - idle.fuel_flow_pph_per_engine
        )

        temp_factor = 1.0
        temp_note = ""
        if oat_c is not None:
            isa_c = 15.0 - 1.9812 * (float(altitude_ft) / 1000.0)
            delta = float(oat_c) - isa_c
            temp_factor = max(0.82, min(1.12, 1.0 - 0.0030 * delta))
            thrust *= temp_factor
            temp_note = f"; estimated temperature correction {temp_factor:.3f}"

        base_prov = combine(mil.provenance, idle.provenance, source="F110 reduced-dry model")
        method = base_prov.method if rpm >= 99.9 and abs(temp_factor - 1.0) < 1e-6 else Method.ESTIMATED
        prov = Provenance(
            method,
            "Legacy F110 deck + reduced-RPM model",
            f"RPM {rpm:.0f}% nonlinear interpolation{temp_note}",
            "Medium at MIL grid points; lower for reduced RPM/temperature corrections",
        )
        return EnginePoint(thrust, ff, rpm, prov)

    def takeoff_eig_reference(
        self,
        rpm_pct: float,
        pressure_altitude_ft: float = 0.0,
        oat_c: float = 15.0,
    ) -> EnginePoint:
        """Return the calibrated static EIG fuel-flow reference for takeoff.

        The source knots are controlled DCS observations near sea level. The
        F-14B EIG displays high-pressure compressor RPM (N2) and fuel flow for
        each engine. A commanded 100% MIL setting uses the highest observed
        99% EIG calibration knot rather than extrapolating false precision.
        """

        commanded_rpm = max(70.0, min(100.0, float(rpm_pct)))
        env = self.takeoff_ff_environment
        reference_pa = float(env["pressure_altitude_ft"].median())
        reference_oat = float(env["oat_c"].median())
        env_rpm_min = float(env["rpm_pct"].min())
        env_rpm_max = float(env["rpm_pct"].max())
        near_environment_anchor = (
            abs(float(pressure_altitude_ft) - reference_pa) <= 750.0
            and abs(float(oat_c) - reference_oat) <= 5.0
            and env_rpm_min <= commanded_rpm <= env_rpm_max
        )
        if near_environment_anchor:
            lookup = regular_grid_interpolate(
                env,
                {"rpm_pct": commanded_rpm},
                "ff_pph_per_engine",
            )
            total_runs = int(env["n_runs"].sum())
            prov = Provenance(
                Method.CALIBRATED,
                "DCS Henderson hot/high F110 EIG observations",
                f"{lookup.detail}; {total_runs} loaded-aircraft observations near "
                f"PA {reference_pa:.0f} ft / {reference_oat:.0f} C",
                "Low-medium; one environment and 95-98% RPM only",
            )
            return EnginePoint(0.0, lookup.value, commanded_rpm, prov)

        observed_rpm = max(
            float(self.takeoff_ff["rpm_pct"].min()),
            min(float(self.takeoff_ff["rpm_pct"].max()), commanded_rpm),
        )
        lookup = regular_grid_interpolate(
            self.takeoff_ff,
            {"rpm_pct": observed_rpm},
            "ff_pph",
        )
        note = f"{lookup.detail} at {observed_rpm:.0f}% observed EIG RPM"
        if commanded_rpm > observed_rpm:
            note += f"; {commanded_rpm:.0f}% MIL command uses the highest measured knot"
        prov = Provenance(
            Method.CALIBRATED,
            "DCS static F110 EIG fuel-flow calibration",
            note,
            "Medium near the Batumi sea-level calibration knots; advisory away from them",
        )
        return EnginePoint(0.0, lookup.value, observed_rpm, prov)

    def total(self, *args, engines: int = 2, **kwargs) -> EnginePoint:
        p = self.point(*args, **kwargs)
        return EnginePoint(
            p.thrust_lbf_per_engine * engines,
            p.fuel_flow_pph_per_engine * engines,
            p.rpm_pct,
            p.provenance,
        )
