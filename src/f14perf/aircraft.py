from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json

from .loadout import Loadout, STATION_ORDER


DEFAULT_CREW_OPERATING_ITEMS_LB = 440.0
INTERNAL_FUEL_CAPACITY_LB = 16_200.0


@dataclass(frozen=True)
class VariantDefinition:
    variant: str
    empty_weight_lb: float
    internal_fuel_capacity_lb: float
    maximum_gross_weight_lb: float
    field_landing_limit_lb: float
    carrier_landing_limit_lb: float
    weight_source: str
    carrier_limit_source: str


VARIANT_CATALOG = {
    "F-14B": VariantDefinition(
        variant="F-14B",
        empty_weight_lb=41_780.0,
        internal_fuel_capacity_lb=INTERNAL_FUEL_CAPACITY_LB,
        maximum_gross_weight_lb=74_349.0,
        field_landing_limit_lb=60_000.0,
        carrier_landing_limit_lb=51_800.0,
        weight_source="Heatblur F-14 technical specification",
        carrier_limit_source="NAVAIR unmodified-aircraft carrier/FCLP limit",
    ),
    "F-14B(U)": VariantDefinition(
        variant="F-14B(U)",
        empty_weight_lb=41_780.0,
        internal_fuel_capacity_lb=INTERNAL_FUEL_CAPACITY_LB,
        maximum_gross_weight_lb=74_349.0,
        field_landing_limit_lb=60_000.0,
        carrier_landing_limit_lb=54_000.0,
        weight_source="Heatblur F-14B technical specification; B(U) delta not established",
        carrier_limit_source="NAVAIR AYC-679/AYC-805 modified-aircraft carrier/FCLP limit",
    ),
}


@dataclass(frozen=True)
class AircraftState:
    """Single source of truth for aircraft configuration and phase weights."""

    variant: str
    loadout: Loadout
    internal_fuel_lb: float
    external_fuel_lb: float = 0.0
    expected_recovery_fuel_lb: float = 0.0
    crew_operating_items_lb: float = DEFAULT_CREW_OPERATING_ITEMS_LB
    gross_weight_override_lb: float | None = None

    def __post_init__(self) -> None:
        if self.variant not in VARIANT_CATALOG:
            raise ValueError(f"Unsupported F-14 variant: {self.variant}")
        if self.loadout.variant != self.variant:
            raise ValueError("Aircraft variant and loadout variant must match")
        for label, value in (
            ("internal fuel", self.internal_fuel_lb),
            ("external fuel", self.external_fuel_lb),
            ("expected recovery fuel", self.expected_recovery_fuel_lb),
            ("crew and operating items", self.crew_operating_items_lb),
        ):
            if float(value) < 0:
                raise ValueError(f"{label} cannot be negative")
        if self.internal_fuel_lb > self.definition.internal_fuel_capacity_lb + 0.1:
            raise ValueError(
                f"Internal fuel exceeds the {self.definition.internal_fuel_capacity_lb:,.0f} lb capacity"
            )
        if self.external_fuel_lb > self.loadout.external_fuel_capacity_lb + 0.1:
            raise ValueError("External fuel exceeds the capacity of the selected external tanks")
        if self.expected_recovery_fuel_lb > self.recovery_fuel_capacity_lb + 0.1:
            raise ValueError("Expected recovery fuel exceeds the capacity of the retained fuel system")
        if self.gross_weight_override_lb is not None and self.gross_weight_override_lb <= 0:
            raise ValueError("Gross-weight override must be positive")

    @property
    def definition(self) -> VariantDefinition:
        return VARIANT_CATALOG[self.variant]

    @property
    def total_launch_fuel_lb(self) -> float:
        return self.internal_fuel_lb + self.external_fuel_lb

    @property
    def launch_fuel_capacity_lb(self) -> float:
        return self.definition.internal_fuel_capacity_lb + self.loadout.external_fuel_capacity_lb

    @property
    def recovery_fuel_capacity_lb(self) -> float:
        return self.definition.internal_fuel_capacity_lb + self.loadout.recovery_external_fuel_capacity_lb

    @property
    def calculated_launch_zero_fuel_weight_lb(self) -> float:
        return (
            self.definition.empty_weight_lb
            + self.crew_operating_items_lb
            + self.loadout.launch_payload_weight_lb
        )

    @property
    def calculated_launch_gross_weight_lb(self) -> float:
        return self.calculated_launch_zero_fuel_weight_lb + self.total_launch_fuel_lb

    @property
    def override_adjustment_lb(self) -> float:
        if self.gross_weight_override_lb is None:
            return 0.0
        return float(self.gross_weight_override_lb) - self.calculated_launch_gross_weight_lb

    @property
    def launch_zero_fuel_weight_lb(self) -> float:
        return self.calculated_launch_zero_fuel_weight_lb + self.override_adjustment_lb

    @property
    def launch_gross_weight_lb(self) -> float:
        return self.launch_zero_fuel_weight_lb + self.total_launch_fuel_lb

    @property
    def recovery_zero_fuel_weight_lb(self) -> float:
        return (
            self.definition.empty_weight_lb
            + self.crew_operating_items_lb
            + self.loadout.recovery_payload_weight_lb
            + self.override_adjustment_lb
        )

    @property
    def expected_recovery_gross_weight_lb(self) -> float:
        return self.recovery_zero_fuel_weight_lb + self.expected_recovery_fuel_lb

    @property
    def launch_drag_index(self) -> float:
        return self.loadout.model_drag_index

    @property
    def recovery_drag_index(self) -> float:
        return self.loadout.recovery_model_drag_index

    @property
    def drag_state(self) -> str:
        if self.loadout.is_clean:
            return "CLEAN"
        if self.loadout.drag_data_valid:
            return f"PUBLISHED DI {self.launch_drag_index:.0f}"
        return "PROVISIONAL STORE DRAG"

    @property
    def config_id(self) -> str:
        payload = {
            "variant": self.variant,
            "stations": [(station, self.loadout.stations[station]) for station in STATION_ORDER],
            "recovery": [
                (station, self.loadout.recovery_dispositions[station])
                for station in STATION_ORDER
            ],
            "internal_fuel_lb": round(self.internal_fuel_lb, 1),
            "external_fuel_lb": round(self.external_fuel_lb, 1),
            "recovery_fuel_lb": round(self.expected_recovery_fuel_lb, 1),
            "crew_items_lb": round(self.crew_operating_items_lb, 1),
            "override_lb": None if self.gross_weight_override_lb is None else round(self.gross_weight_override_lb, 1),
        }
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:10].upper()

    def with_recovery_fuel(self, fuel_lb: float) -> "AircraftState":
        bounded = max(0.0, min(float(fuel_lb), self.recovery_fuel_capacity_lb))
        return replace(self, expected_recovery_fuel_lb=bounded)

    @property
    def weight_breakdown(self) -> dict[str, float]:
        return {
            "Aircraft empty weight": self.definition.empty_weight_lb,
            "Crew / operating items": self.crew_operating_items_lb,
            "Stores / adapters": self.loadout.launch_payload_weight_lb,
            "Internal fuel": self.internal_fuel_lb,
            "External fuel": self.external_fuel_lb,
            "Advanced override adjustment": self.override_adjustment_lb,
            "Launch gross weight": self.launch_gross_weight_lb,
        }

    @property
    def warnings(self) -> list[str]:
        warnings: list[str] = []
        if self.variant == "F-14B(U)":
            warnings.append(
                "F-14B(U) currently uses the published F-14B empty-weight baseline; a supported DCS variant delta has not been established."
            )
        if self.loadout.has_nominal_weights:
            warnings.append(
                "Loaded-store masses are nominal planning values pending a controlled DCS payload-delta audit."
            )
        if self.loadout.has_unresolved_adapter_weights:
            warnings.append(
                "Rack, pallet, and adapter masses remain explicit unresolved DCS deltas and are not silently estimated."
            )
        if not self.loadout.drag_data_valid:
            warnings.append(
                "Individual-store drag is provisional; affected takeoff, climb, and cruise outputs remain guarded."
            )
        if abs(self.override_adjustment_lb) > 0.1:
            warnings.append(
                f"Advanced DCS gross-weight override is active ({self.override_adjustment_lb:+,.0f} lb adjustment) and is carried through recovery."
            )
        if self.launch_gross_weight_lb > self.definition.maximum_gross_weight_lb:
            warnings.append(
                f"Launch gross weight exceeds the {self.definition.maximum_gross_weight_lb:,.0f} lb published maximum."
            )
        if self.expected_recovery_gross_weight_lb > self.definition.field_landing_limit_lb:
            warnings.append(
                f"Expected recovery weight exceeds the {self.definition.field_landing_limit_lb:,.0f} lb field landing limit."
            )
        return warnings
