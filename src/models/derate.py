"""Compatibility facade for the discrete v3 takeoff-rating model.

The former module searched every one-percent RPM value and could escalate to
afterburner. That behavior is intentionally disabled. Existing imports keep a
small facade, but callers must now use an exact discrete rating or AUTO.
"""

from __future__ import annotations

from src.f14perf.engine import F110Deck
from src.models.takeoff_model import TakeoffModel


class DerateCalculator:
    def __init__(self, aircraft_type: str, engine_type: str, config_path: str | None = None):
        self.aircraft_type = aircraft_type
        self.engine_type = engine_type
        self.config_path = config_path
        self.engine = F110Deck()

    def _rating(self, value: str | float) -> str:
        if isinstance(value, (int, float)):
            return self.engine.rating_for_rpm(float(value))
        key = self.engine.normalize_takeoff_rating(str(value))
        if key not in self.engine.rating_ids():
            raise ValueError(f"Unsupported discrete takeoff rating: {value}")
        return key

    def compute_manual_derate(self, rpm: str | float, takeoff_conditions: dict) -> dict:
        rating = self._rating(rpm)
        result = TakeoffModel(
            aircraft_type=self.aircraft_type,
            engine_type=self.engine_type,
        ).compute_takeoff(thrust_rating=rating, **takeoff_conditions)
        return self._format_mission_card(result)

    def compute_auto_derate(self, takeoff_conditions: dict) -> dict:
        result = TakeoffModel(
            aircraft_type=self.aircraft_type,
            engine_type=self.engine_type,
        ).compute_takeoff(thrust_mode="AUTO", **takeoff_conditions)
        return self._format_mission_card(result)

    @staticmethod
    def _format_mission_card(result: dict) -> dict:
        return {
            "Thrust Rating": result.get("thrust_setting"),
            "Fuel Flow (pph/engine)": result.get("fuel_flow_pph_per_engine"),
            "RPM Cross-check": result.get("rpm_reference"),
            "V1": "WITHHELD",
            "Vr (KIAS)": result.get("vr_kt"),
            "V2 (KIAS)": result.get("v2_kt"),
            "Vfs (KIAS)": result.get("vfs_kt"),
            "Climb Gradient (ft/nm)": result.get("climb_gradient_ft_nm"),
            "Trim Setting": f"{float(result.get('stabilizer_trim_anu', 0.0)):.1f} ANU",
            "OEI Climb Speed (KIAS)": result.get("oei_climb_speed_kt"),
            "OEI Configuration": "GEAR UP / MILITARY on operating engine",
            "Planning Status": (
                "PLANNING HOLD"
                if not result.get("takeoff_data_valid", False)
                else ("REFERENCE ONLY" if result.get("feasible", False) else "LIMIT EXCEEDED")
            ),
            "Warnings": result.get("warnings", []),
        }
