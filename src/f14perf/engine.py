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


@dataclass(frozen=True)
class TakeoffRating:
    """A discrete dry takeoff rating and its cockpit indication reference."""

    rating_id: str
    display_name: str
    nominal_rpm_pct: float
    fuel_flow_pph_per_engine: float
    selection_order: int
    allowed_flaps: tuple[str, ...]
    condition_calibrated: bool
    rpm_reference: str
    evidence_class: str
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
    TAKEOFF_RATING_REQUIRED = {
        "rating_id",
        "display_name",
        "nominal_rpm_pct",
        "standard_ff_pph_per_engine",
        "selection_order",
        "allowed_flaps",
        "evidence_class",
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
        self.takeoff_ratings = read_csv("f110_takeoff_ratings.csv", data_dir)
        self.takeoff_ratings.columns = [
            str(c).strip().lower() for c in self.takeoff_ratings.columns
        ]
        require_columns(
            self.takeoff_ratings,
            self.TAKEOFF_RATING_REQUIRED,
            "f110_takeoff_ratings.csv",
        )
        self.takeoff_ratings["rating_id"] = (
            self.takeoff_ratings["rating_id"].astype(str).str.upper()
        )
        self._validate_takeoff_ratings()

    def _validate_takeoff_ratings(self) -> None:
        """Keep the standardized ratings tied to their evidence records."""

        ratings = self.takeoff_ratings
        if ratings["rating_id"].duplicated().any():
            raise ValueError("Takeoff rating identifiers must be unique.")
        if ratings["selection_order"].duplicated().any():
            raise ValueError("Takeoff rating selection order must be unique.")
        if "MIL" not in set(ratings["rating_id"]):
            raise ValueError("The discrete takeoff rating set must include MIL.")

        observed = {
            round(float(row.rpm_pct), 1): round(float(row.ff_pph), 1)
            for row in self.takeoff_ff.itertuples(index=False)
        }
        for row in ratings.itertuples(index=False):
            if row.rating_id == "MIL":
                if round(float(row.standard_ff_pph_per_engine)) != 10_100:
                    raise ValueError("MIL takeoff rating must retain the NATOPS 10,100 PPH/engine reference.")
                continue
            rpm = round(float(row.nominal_rpm_pct), 1)
            ff = round(float(row.standard_ff_pph_per_engine), 1)
            if observed.get(rpm) != ff:
                raise ValueError(
                    f"{row.rating_id} must match a DCS-observed static FF/RPM knot; "
                    f"got {rpm:.1f}% / {ff:.0f} PPH."
                )

    @staticmethod
    def normalize_takeoff_rating(rating: str) -> str:
        key = str(rating).strip().upper().replace("-", "_").replace(" ", "_")
        aliases = {
            "D1": "DERATE_1",
            "D2": "DERATE_2",
            "D3": "DERATE_3",
            "DERATE1": "DERATE_1",
            "DERATE2": "DERATE_2",
            "DERATE3": "DERATE_3",
            "MILITARY": "MIL",
        }
        return aliases.get(key, key)

    def rating_ids(self, flaps: str | None = None) -> tuple[str, ...]:
        rows = self.takeoff_ratings.sort_values("selection_order")
        if flaps is not None:
            flap = str(flaps).upper()
            rows = rows[
                rows["allowed_flaps"].astype(str).map(
                    lambda value: flap in value.upper().split("|")
                )
            ]
        return tuple(rows["rating_id"].astype(str))

    def rating_for_rpm(self, rpm_pct: float) -> str:
        """Resolve legacy callers only when they request an exact discrete knot."""

        rpm = float(rpm_pct)
        matches = self.takeoff_ratings[
            (self.takeoff_ratings["nominal_rpm_pct"].astype(float) - rpm).abs() <= 0.05
        ]
        if matches.empty:
            allowed = ", ".join(
                f"{row.display_name} ({float(row.nominal_rpm_pct):.0f}%)"
                for row in self.takeoff_ratings.sort_values("selection_order").itertuples(index=False)
            )
            raise ValueError(
                "Continuously variable takeoff RPM is disabled. "
                f"Use one of the discrete ratings: {allowed}."
            )
        return str(matches.iloc[0]["rating_id"])

    def takeoff_rating(
        self,
        rating: str,
        pressure_altitude_ft: float = 0.0,
        oat_c: float = 15.0,
    ) -> TakeoffRating:
        """Return an evidence-bounded FF-first indication for one rating.

        Reduced ratings are defined by observed DCS EIG knots. Near the
        Henderson hot/high observation point, only ratings whose nominal RPM
        falls inside the measured 95-98 percent interval receive a local FF
        target. Away from either observation envelope, the standard FF is kept
        as a reference but is explicitly not condition-calibrated.
        """

        key = self.normalize_takeoff_rating(rating)
        matches = self.takeoff_ratings[self.takeoff_ratings["rating_id"] == key]
        if matches.empty:
            raise ValueError(f"Unsupported takeoff rating: {rating}")
        row = matches.iloc[0]
        nominal_rpm = float(row["nominal_rpm_pct"])
        standard_ff = float(row["standard_ff_pph_per_engine"])
        allowed_flaps = tuple(str(row["allowed_flaps"]).upper().split("|"))

        if key == "MIL":
            provenance = Provenance(
                Method.DIRECT_TABLE,
                "NAVAIR 01-F14AAP-1, sections 2.11.2-2.11.7",
                "Normal on-deck MIL indications: approximately 10,100 PPH per engine, "
                "95-104% N2, and 3-10% nozzle",
                "High for the published normal indication; use the MIL detent and matched engine indications",
            )
            return TakeoffRating(
                key,
                str(row["display_name"]),
                nominal_rpm,
                standard_ff,
                int(row["selection_order"]),
                allowed_flaps,
                True,
                "95-104% N2",
                str(row["evidence_class"]),
                provenance,
            )

        env = self.takeoff_ff_environment
        reference_pa = float(env["pressure_altitude_ft"].median())
        reference_oat = float(env["oat_c"].median())
        near_henderson = (
            abs(float(pressure_altitude_ft) - reference_pa) <= 750.0
            and abs(float(oat_c) - reference_oat) <= 5.0
        )
        env_min_rpm = float(env["rpm_pct"].min())
        env_max_rpm = float(env["rpm_pct"].max())
        if near_henderson and env_min_rpm <= nominal_rpm <= env_max_rpm:
            lookup = regular_grid_interpolate(
                env,
                {"rpm_pct": nominal_rpm},
                "ff_pph_per_engine",
            )
            provenance = Provenance(
                Method.CALIBRATED,
                "DCS Henderson hot/high F110 EIG observations",
                f"{lookup.detail}; local indication only near PA {reference_pa:.0f} ft / "
                f"{reference_oat:.0f} C",
                "Low-medium; this is an engine-indication reference, not proof of delivered thrust",
            )
            return TakeoffRating(
                key,
                str(row["display_name"]),
                nominal_rpm,
                float(lookup.value),
                int(row["selection_order"]),
                allowed_flaps,
                True,
                f"approximately {nominal_rpm:.0f}% N2",
                str(row["evidence_class"]),
                provenance,
            )

        near_standard = (
            abs(float(pressure_altitude_ft)) <= 750.0
            and abs(float(oat_c) - 15.0) <= 5.0
        )
        if near_standard:
            provenance = Provenance(
                Method.CALIBRATED,
                "DCS Batumi near-sea-level ISA static EIG observations",
                f"Direct discrete knot: {standard_ff:.0f} PPH/engine at approximately "
                f"{nominal_rpm:.0f}% indicated N2",
                "Medium for the cockpit indication; takeoff thrust and distance remain model-derived",
            )
            return TakeoffRating(
                key,
                str(row["display_name"]),
                nominal_rpm,
                standard_ff,
                int(row["selection_order"]),
                allowed_flaps,
                True,
                f"approximately {nominal_rpm:.0f}% N2",
                str(row["evidence_class"]),
                provenance,
            )

        provenance = Provenance(
            Method.ESTIMATED,
            "DCS Batumi static EIG reference outside its observation envelope",
            f"Standard reference retained: {standard_ff:.0f} PPH/engine at "
            f"approximately {nominal_rpm:.0f}% N2; no PA/OAT correction fitted",
            "Low; use MIL until a matching environment sweep is recorded",
        )
        return TakeoffRating(
            key,
            str(row["display_name"]),
            nominal_rpm,
            standard_ff,
            int(row["selection_order"]),
            allowed_flaps,
            False,
            f"standard-point reference approximately {nominal_rpm:.0f}% N2",
            str(row["evidence_class"]),
            provenance,
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
        if commanded_rpm >= 99.5:
            return EnginePoint(
                0.0,
                10_100.0,
                100.0,
                Provenance(
                    Method.DIRECT_TABLE,
                    "NAVAIR 01-F14AAP-1, sections 2.11.2-2.11.7",
                    "Normal on-deck MIL indications: approximately 10,100 PPH per engine, "
                    "95-104% N2, and 3-10% nozzle",
                    "High for the published normal indication; use matched engine indications and the MIL detent",
                ),
            )
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

    def rpm_for_takeoff_ff(
        self,
        fuel_flow_pph_per_engine: float,
        pressure_altitude_ft: float = 0.0,
        oat_c: float = 15.0,
    ) -> EnginePoint:
        """Invert the observed dry-power EIG knots for an FF-first setup.

        Fuel flow is the displayed takeoff-setting cue. RPM is returned only as
        a secondary cross-check. The inverse is limited to the measured range;
        MIL is handled separately by :meth:`takeoff_eig_reference`.
        """

        target_ff = float(fuel_flow_pph_per_engine)
        env = self.takeoff_ff_environment
        reference_pa = float(env["pressure_altitude_ft"].median())
        reference_oat = float(env["oat_c"].median())
        near_environment_anchor = (
            abs(float(pressure_altitude_ft) - reference_pa) <= 750.0
            and abs(float(oat_c) - reference_oat) <= 5.0
            and float(env["ff_pph_per_engine"].min()) <= target_ff
            <= float(env["ff_pph_per_engine"].max())
        )
        if near_environment_anchor:
            lookup = regular_grid_interpolate(
                env,
                {"ff_pph_per_engine": target_ff},
                "rpm_pct",
            )
            return EnginePoint(
                0.0,
                target_ff,
                lookup.value,
                Provenance(
                    Method.CALIBRATED,
                    "DCS Henderson hot/high F110 EIG observations",
                    f"Inverse FF-to-RPM interpolation; {lookup.detail}",
                    "Low-medium; one environment and the 5,250-6,000 PPH/engine band only",
                ),
            )

        ff_min = float(self.takeoff_ff["ff_pph"].min())
        ff_max = float(self.takeoff_ff["ff_pph"].max())
        bounded_ff = max(ff_min, min(ff_max, target_ff))
        lookup = regular_grid_interpolate(
            self.takeoff_ff,
            {"ff_pph": bounded_ff},
            "rpm_pct",
        )
        detail = f"Inverse FF-to-RPM interpolation; {lookup.detail}"
        if bounded_ff != target_ff:
            detail += f"; target bounded to observed {bounded_ff:.0f} PPH/engine"
        return EnginePoint(
            0.0,
            target_ff,
            lookup.value,
            Provenance(
                Method.CALIBRATED,
                "DCS static F110 EIG fuel-flow calibration",
                detail,
                "Medium near the Batumi sea-level knots; advisory away from them",
            ),
        )
