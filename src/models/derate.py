import json
import os
from src.models.takeoff_model import TakeoffModel
from src.utils.data_loaders import load_takeoff_data


class DerateCalculator:
    """
    Handles reduced thrust (derate) takeoff calculations for F-14 performance toolkit.
    """

    def __init__(self, aircraft_type: str, engine_type: str, config_path: str = None):
        self.aircraft_type = aircraft_type
        self.engine_type = engine_type
        self.config_path = config_path or os.path.join(
            os.path.dirname(__file__), "derate_config.json"
        )
        self.config = self._load_config()

    def _load_config(self):
        """Load derate configuration from JSON."""
        if os.path.exists(self.config_path):
            with open(self.config_path, "r") as f:
                return json.load(f)
        # Default guardrails
        return {"min_rpm": 85, "max_rpm": 99, "rpm_step": 1}

    def compute_manual_derate(self, rpm: float, takeoff_conditions: dict) -> dict:
        """
        Compute a manual derate at given RPM.
        Returns structured mission card output.
        """
        # Validate RPM
        if not (self.config["min_rpm"] <= rpm <= self.config["max_rpm"]):
            raise ValueError(f"RPM {rpm}% outside allowable derate range.")

        takeoff_model = TakeoffModel(
            aircraft_type=self.aircraft_type,
            engine_type=self.engine_type,
            **takeoff_conditions
        )

        results = takeoff_model.compute_takeoff(rpm=rpm)

        # Add mission card structure
        mission_card = self._format_mission_card(results, rpm, derate_type="MANUAL")
        return mission_card

    def compute_auto_derate(self, takeoff_conditions: dict) -> dict:
        """
        Compute the lowest RPM that satisfies climb gradient ≥300 ft/nm.
        If MIL+FULL flaps <200 ft/nm, escalate to AB.
        """
        best_results = None
        min_rpm = self.config["min_rpm"]
        max_rpm = self.config["max_rpm"]
        step = self.config["rpm_step"]

        for rpm in range(max_rpm, min_rpm - 1, -step):
            takeoff_model = TakeoffModel(
                aircraft_type=self.aircraft_type,
                engine_type=self.engine_type,
                **takeoff_conditions
            )
            results = takeoff_model.compute_takeoff(rpm=rpm)

            if results["Climb Gradient (ft/nm)"] >= 300:
                best_results = self._format_mission_card(results, rpm, derate_type="AUTO")
                break

        # If no valid derate, check if MIL+FULL flaps <200
        if not best_results:
            takeoff_model = TakeoffModel(
                aircraft_type=self.aircraft_type,
                engine_type=self.engine_type,
                **takeoff_conditions
            )
            results = takeoff_model.compute_takeoff(rpm=max_rpm)

            if results["Climb Gradient (ft/nm)"] < 200:
                results["Warnings"] = "❌ RED: Gradient <200 ft/nm — Escalating to Afterburner"
                best_results = self._format_mission_card(results, 100, derate_type="AFTERBURNER")
            else:
                results["Warnings"] = "Amber caution: Gradient <300 ft/nm, MIL thrust required"
                best_results = self._format_mission_card(results, max_rpm, derate_type="MIL")

        return best_results

    def _format_mission_card(self, results: dict, rpm: float, derate_type: str) -> dict:
        """
        Format results into mission card structure for pilot readability.
        """
        thrust_type = "REDUCED" if derate_type in ["AUTO", "MANUAL"] else derate_type
        warnings = results.get("Warnings", "")
        trim_anu = float(results.get("stabilizer_trim_anu", 0.0))

        return {
            "Thrust Type": thrust_type,
            "Takeoff RPM (%)": rpm,
            "Fuel Flow (pph/engine)": results.get("Fuel Flow (pph/engine)", None),
            "V1 (KCAS)": results.get("V1"),
            "Vr (KCAS)": results.get("Vr"),
            "V2 (KCAS)": results.get("V2"),
            "Vfs (KCAS)": results.get("vfs_kt", results.get("Vfs")),
            "Climb Gradient (ft/nm)": results.get("Climb Gradient (ft/nm)"),
            "Warnings": warnings,
            "Trim Setting": results.get(
                "Trim Setting",
                f"{trim_anu:.1f} ANU before commencing takeoff roll",
            ),
            "OEI Climb Speed (KIAS)": results.get("oei_climb_speed_kt"),
            "OEI Configuration": "GEAR UP / MILITARY on operating engine",
            "Fuel Savings (lbs)": self._compute_fuel_savings(results, rpm),
        }

    def _compute_fuel_savings(self, results: dict, rpm: float) -> float:
        """
        Compute fuel savings vs MIL baseline to 200 nm.
        Placeholder uses delta FF × fixed time factor (to be refined with climb model).
        """
        mil_ff = results.get("Baseline MIL FF", 20000)  # placeholder, refine with climb_model
        reduced_ff = results.get("Fuel Flow (pph/engine)", mil_ff)
        delta_ff = mil_ff - reduced_ff
        flight_time_hr = 0.5  # placeholder for time to 200 nm, refine with climb model
        return round(delta_ff * flight_time_hr * 2, 0)  # ×2 engines
