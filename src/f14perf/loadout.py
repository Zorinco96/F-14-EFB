from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Mapping

from .data import DEFAULT_DATA_DIR, DataError, read_csv, require_columns


STATION_ORDER = ("1A", "1B", "2", "3", "4", "5", "6", "7", "8B", "8A")
RECOVERY_DISPOSITIONS = ("RETAIN", "EXPEND", "JETTISON")
EMPTY_STORE_ID = "EMPTY"


@dataclass(frozen=True)
class StoreDefinition:
    store_id: str
    label: str
    category: str
    nominal_store_weight_lb: float
    retained_residue_weight_lb: float
    station_quantities: Mapping[str, int]
    adapter_family: str
    adapter_weight_lb: float
    external_fuel_capacity_lb: float
    expendable: bool
    jettisonable: bool
    variants: tuple[str, ...]
    provisional_drag_units: float
    inventory_source_class: str
    weight_source_class: str
    adapter_weight_source_class: str
    drag_source_class: str
    source_note: str

    def quantity_for(self, station: str) -> int:
        return int(self.station_quantities.get(station, 0))

    def supports(self, station: str, variant: str) -> bool:
        return self.quantity_for(station) > 0 and variant in self.variants

    @property
    def model_drag_units(self) -> float:
        """Compatibility name for the provisional per-unit drag value."""

        return self.provisional_drag_units

    @property
    def expendable_credit_lb(self) -> float:
        """Maximum per-unit mass removed by expenditure."""

        if not self.expendable:
            return 0.0
        return max(0.0, self.nominal_store_weight_lb - self.retained_residue_weight_lb)


EMPTY_STORE = StoreDefinition(
    store_id=EMPTY_STORE_ID,
    label="Empty station",
    category="EMPTY",
    nominal_store_weight_lb=0.0,
    retained_residue_weight_lb=0.0,
    station_quantities={station: 1 for station in STATION_ORDER},
    adapter_family="NONE",
    adapter_weight_lb=0.0,
    external_fuel_capacity_lb=0.0,
    expendable=False,
    jettisonable=False,
    variants=("F-14B", "F-14B(U)"),
    provisional_drag_units=0.0,
    inventory_source_class="HEATBLUR_DCS",
    weight_source_class="DIRECT",
    adapter_weight_source_class="DIRECT",
    drag_source_class="DIRECT",
    source_note="Explicit empty station selection",
)


REQUIRED_STORE_COLUMNS = {
    "store_id",
    "label",
    "category",
    "nominal_store_weight_lb",
    "retained_residue_weight_lb",
    "adapter_family",
    "adapter_weight_lb",
    "external_fuel_capacity_lb",
    "expendable",
    "jettisonable",
    "variants",
    "provisional_drag_units",
    "inventory_source_class",
    "weight_source_class",
    "adapter_weight_source_class",
    "drag_source_class",
    "source_note",
    *{f"station_{station.lower()}_qty" for station in STATION_ORDER},
}


def _bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


@lru_cache(maxsize=4)
def _load_store_catalog(data_dir_text: str) -> dict[str, StoreDefinition]:
    data_dir = Path(data_dir_text)
    df = read_csv("f14_stores.csv", data_dir)
    require_columns(df, REQUIRED_STORE_COLUMNS, "f14_stores.csv")
    if df["store_id"].duplicated().any():
        duplicates = sorted(df.loc[df["store_id"].duplicated(), "store_id"].astype(str))
        raise DataError(f"f14_stores.csv contains duplicate store IDs: {duplicates}")

    catalog: dict[str, StoreDefinition] = {EMPTY_STORE_ID: EMPTY_STORE}
    for row in df.to_dict(orient="records"):
        store_id = str(row["store_id"]).strip().upper()
        station_quantities = {
            station: int(row[f"station_{station.lower()}_qty"])
            for station in STATION_ORDER
        }
        variants = tuple(part.strip() for part in str(row["variants"]).split("|") if part.strip())
        if not variants:
            raise DataError(f"{store_id} has no supported variant")
        catalog[store_id] = StoreDefinition(
            store_id=store_id,
            label=str(row["label"]).strip(),
            category=str(row["category"]).strip(),
            nominal_store_weight_lb=float(row["nominal_store_weight_lb"]),
            retained_residue_weight_lb=float(row["retained_residue_weight_lb"]),
            station_quantities=station_quantities,
            adapter_family=str(row["adapter_family"]).strip(),
            adapter_weight_lb=float(row["adapter_weight_lb"]),
            external_fuel_capacity_lb=float(row["external_fuel_capacity_lb"]),
            expendable=_bool(row["expendable"]),
            jettisonable=_bool(row["jettisonable"]),
            variants=variants,
            provisional_drag_units=float(row["provisional_drag_units"]),
            inventory_source_class=str(row["inventory_source_class"]).strip(),
            weight_source_class=str(row["weight_source_class"]).strip(),
            adapter_weight_source_class=str(row["adapter_weight_source_class"]).strip(),
            drag_source_class=str(row["drag_source_class"]).strip(),
            source_note=str(row["source_note"]).strip(),
        )
    return catalog


def store_catalog(data_dir: Path | str | None = None) -> dict[str, StoreDefinition]:
    base = Path(data_dir) if data_dir is not None else DEFAULT_DATA_DIR
    return dict(_load_store_catalog(str(base.resolve())))


STORE_CATALOG = store_catalog()


def station_options(station: str, variant: str = "F-14B(U)") -> tuple[str, ...]:
    if station not in STATION_ORDER:
        raise ValueError(f"Unsupported F-14 station: {station}")
    if variant not in {"F-14B", "F-14B(U)"}:
        raise ValueError(f"Unsupported F-14 variant: {variant}")
    options = [EMPTY_STORE_ID]
    options.extend(
        store_id
        for store_id, definition in STORE_CATALOG.items()
        if store_id != EMPTY_STORE_ID and definition.supports(station, variant)
    )
    return tuple(options)


# Compatibility view for callers that previously consumed a static option map.
# New UI code should call station_options so variant filtering remains explicit.
STATION_OPTIONS = {
    station: station_options(station, "F-14B(U)") for station in STATION_ORDER
}


def station_option_label(station: str, store_id: str) -> str:
    definition = STORE_CATALOG[store_id]
    if store_id == EMPTY_STORE_ID:
        return definition.label
    quantity = definition.quantity_for(station)
    adapter = "" if definition.adapter_family in {"", "NONE"} else f" | {definition.adapter_family.replace('_', ' ')}"
    prefix = f"{quantity} x " if quantity > 1 else ""
    return f"{prefix}{definition.label}{adapter}"


# Presets follow the Heatblur SCL count patterns. They are editable station
# selections, not separate performance categories.
LOADOUT_PRESETS: dict[str, dict[str, str]] = {
    "Clean": {},
    "AAW01 | BFM (0/0/2)": {"1A": "AIM9M", "8A": "AIM9M"},
    "AAW02 | Light CAP (1/1/1)": {"1A": "AIM9M", "1B": "AIM7M", "3": "AIM54C47"},
    "AAW03 | Light CAP (1/2/2)": {"1A": "AIM9M", "1B": "AIM7M", "3": "AIM54C47", "8B": "AIM7M", "8A": "AIM9M"},
    "AAW04 | Medium CAP (2/3/2)": {"1A": "AIM9M", "1B": "AIM7M", "3": "AIM54C47", "4": "AIM7M", "6": "AIM54C47", "8B": "AIM7M", "8A": "AIM9M"},
    "AAW05 | Heavy CAP (4/2/2)": {"1A": "AIM9M", "1B": "AIM7M", "3": "AIM54C47", "4": "AIM54C47", "5": "AIM54C47", "6": "AIM54C47", "8B": "AIM7M", "8A": "AIM9M"},
    "AAW06 | Six Shooter (6/0/2)": {"1A": "AIM9M", "1B": "AIM54C47", "3": "AIM54C47", "4": "AIM54C47", "5": "AIM54C47", "6": "AIM54C47", "8B": "AIM54C47", "8A": "AIM9M"},
    "AG01 | Light Strike": {"1A": "AIM9M", "1B": "AIM54C47", "3": "GBU12", "6": "GBU16", "8A": "AIM9M"},
    "AG02 | Medium CAS": {"1A": "AIM9M", "1B": "AIM54C47", "3": "GBU12", "4": "GBU38", "5": "GBU38", "6": "GBU12", "8A": "AIM9M"},
    "AG03 | Medium CAS": {"1A": "AIM9M", "1B": "AIM54C47", "3": "GBU16", "4": "GBU38", "5": "GBU38", "6": "GBU16", "8A": "AIM9M"},
    "AG04 | Medium Strike": {"1A": "AIM9M", "1B": "AIM54C47", "3": "GBU31V2", "6": "GBU31V2", "8A": "AIM9M"},
    "AG05 | Heavy CAS": {"1A": "AIM9M", "1B": "AIM54C47", "3": "GBU31V2", "4": "GBU12", "5": "GBU12", "6": "GBU31V2", "8A": "AIM9M"},
    "AG06 | Heavy Strike": {"1A": "AIM9M", "1B": "AIM54C47", "3": "GBU24E", "5": "GBU24E", "8A": "AIM9M"},
    "AG07 | Heavy Strike": {"1A": "AIM9M", "1B": "AIM54C47", "3": "GBU31V2", "4": "GBU31V2", "6": "GBU31V2", "8A": "AIM9M"},
    "AG08 | Four JDAM strike": {"1A": "AIM9M", "3": "GBU31V2", "4": "GBU31V2", "5": "GBU31V2", "6": "GBU31V2"},
    "AG09 | Self escort strike": {"1A": "AIM9M", "1B": "AIM7M", "3": "AIM54C47", "6": "GBU38", "8B": "AIM54C47", "8A": "AIM9M"},
    "TARPS01 | TARPS": {"1A": "AIM9M", "1B": "AIM7M", "5": "TARPS", "8B": "AIM7M", "8A": "AIM9M"},
    "TNG01 | ACMI": {"8A": "TCTS"},
    "TNG02 | ACMI + self protection": {"1A": "AIM9M", "1B": "AIM54C47", "8A": "AIM9M", "8B": "TCTS"},
    "SPL01 | SARH (0/4/4)": {"1A": "AIM9M", "1B": "AIM9M", "3": "AIM7M", "4": "AIM7M", "5": "AIM7M", "6": "AIM7M", "8B": "AIM9M", "8A": "AIM9M"},
    "SPL02 | Four Sidewinders": {"1A": "AIM9M", "1B": "AIM9M", "8B": "AIM9M", "8A": "AIM9M"},
    "Fleet defense | 6 AIM-54 + 2 tanks": {"1B": "AIM54C47", "2": "FPU1", "3": "AIM54C47", "4": "AIM54C47", "5": "AIM54C47", "6": "AIM54C47", "7": "FPU1", "8B": "AIM54C47"},
    "2 external tanks + 2 AIM-9": {"1A": "AIM9M", "2": "FPU1", "7": "FPU1", "8A": "AIM9M"},
}


def presets_for_variant(variant: str) -> tuple[str, ...]:
    compatible: list[str] = []
    for name, stations in LOADOUT_PRESETS.items():
        try:
            Loadout(stations, variant=variant)
        except ValueError:
            continue
        compatible.append(name)
    return tuple(compatible)


@dataclass(frozen=True)
class Loadout:
    stations: Mapping[str, str]
    variant: str = "F-14B(U)"
    recovery_dispositions: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.variant not in {"F-14B", "F-14B(U)"}:
            raise ValueError(f"Unsupported F-14 variant: {self.variant}")
        normalized = {station: str(self.stations.get(station, EMPTY_STORE_ID)).upper() for station in STATION_ORDER}
        for station, store_id in normalized.items():
            if store_id not in STORE_CATALOG:
                raise ValueError(f"Unsupported F-14 store: {store_id}")
            if store_id not in station_options(station, self.variant):
                raise ValueError(f"{store_id} is not supported on F-14 station {station} for {self.variant}")

        # Aft tunnel Phoenix pallets require the corresponding forward pallet.
        # An explicit empty pallet or a pallet-carried store satisfies this DCS
        # relationship without forcing a weapon onto the forward station.
        for aft, forward in (("4", "3"), ("5", "6")):
            if normalized[aft].startswith("AIM54"):
                forward_store = STORE_CATALOG[normalized[forward]]
                if forward_store.adapter_family not in {
                    "PHOENIX_ADAPTER",
                    "PHOENIX_PALLET",
                    "BRU-32_PHOENIX_PALLET",
                }:
                    raise ValueError(
                        f"AIM-54 on station {aft} requires a forward Phoenix pallet on station {forward}"
                    )

        dispositions = {station: str(self.recovery_dispositions.get(station, "RETAIN")).upper() for station in STATION_ORDER}
        for station, disposition in dispositions.items():
            if disposition not in RECOVERY_DISPOSITIONS:
                raise ValueError(f"Unsupported recovery disposition: {disposition}")
            store = STORE_CATALOG[normalized[station]]
            if disposition == "EXPEND" and not store.expendable:
                raise ValueError(f"{store.label} on station {station} cannot be planned expended")
            if disposition == "JETTISON" and not store.jettisonable:
                raise ValueError(f"{store.label} on station {station} cannot be planned jettisoned")

        object.__setattr__(self, "stations", normalized)
        object.__setattr__(self, "recovery_dispositions", dispositions)

    @property
    def normalized_stations(self) -> dict[str, str]:
        return dict(self.stations)

    @property
    def is_clean(self) -> bool:
        return all(store_id == EMPTY_STORE_ID for store_id in self.stations.values())

    def quantity(self, station: str) -> int:
        return STORE_CATALOG[self.stations[station]].quantity_for(station)

    @property
    def loaded_station_count(self) -> int:
        return sum(store_id != EMPTY_STORE_ID for store_id in self.stations.values())

    @property
    def loaded_store_count(self) -> int:
        return sum(
            self.quantity(station)
            for station, store_id in self.stations.items()
            if store_id != EMPTY_STORE_ID
        )

    @property
    def store_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for station, store_id in self.stations.items():
            if store_id != EMPTY_STORE_ID:
                counts[store_id] = counts.get(store_id, 0) + self.quantity(station)
        return counts

    def _station_launch_weight(self, station: str) -> float:
        store = STORE_CATALOG[self.stations[station]]
        return store.nominal_store_weight_lb * self.quantity(station) + store.adapter_weight_lb

    def _station_recovery_weight(self, station: str) -> float:
        store = STORE_CATALOG[self.stations[station]]
        disposition = self.recovery_dispositions[station]
        if disposition == "RETAIN":
            store_mass = store.nominal_store_weight_lb * self.quantity(station)
        elif disposition == "EXPEND":
            store_mass = store.retained_residue_weight_lb * self.quantity(station)
        else:
            store_mass = 0.0
        return store_mass + store.adapter_weight_lb

    @property
    def launch_payload_weight_lb(self) -> float:
        return sum(self._station_launch_weight(station) for station in STATION_ORDER)

    @property
    def recovery_payload_weight_lb(self) -> float:
        return sum(self._station_recovery_weight(station) for station in STATION_ORDER)

    @property
    def planned_removed_weight_lb(self) -> float:
        return max(0.0, self.launch_payload_weight_lb - self.recovery_payload_weight_lb)

    @property
    def expendable_credit_weight_lb(self) -> float:
        """Maximum possible expenditure credit, independent of the recovery plan."""

        return sum(
            STORE_CATALOG[store_id].expendable_credit_lb * self.quantity(station)
            for station, store_id in self.stations.items()
        )

    @property
    def external_fuel_capacity_lb(self) -> float:
        return sum(
            STORE_CATALOG[store_id].external_fuel_capacity_lb * self.quantity(station)
            for station, store_id in self.stations.items()
        )

    @property
    def recovery_external_fuel_capacity_lb(self) -> float:
        return sum(
            STORE_CATALOG[store_id].external_fuel_capacity_lb * self.quantity(station)
            for station, store_id in self.stations.items()
            if self.recovery_dispositions[station] == "RETAIN"
        )

    @property
    def provisional_drag_index(self) -> float:
        return sum(
            STORE_CATALOG[store_id].provisional_drag_units * self.quantity(station)
            for station, store_id in self.stations.items()
        )

    @property
    def recovery_provisional_drag_index(self) -> float:
        return sum(
            STORE_CATALOG[store_id].provisional_drag_units * self.quantity(station)
            for station, store_id in self.stations.items()
            if self.recovery_dispositions[station] == "RETAIN"
        )

    @property
    def natops_drag_reference(self) -> tuple[float, str] | None:
        counts = self.store_counts
        aim7_count = sum(counts.get(key, 0) for key in ("AIM7E2", "AIM7F", "AIM7M"))
        aim54_count = sum(counts.get(key, 0) for key in ("AIM54A47", "AIM54A60", "AIM54C47"))
        tank_count = counts.get("FPU1", 0)
        total = sum(counts.values())
        if aim7_count == 4 and total == 4:
            return 8.0, "NAVAIR 01-F14AAP-1 Figure 14-1: four AIM-7"
        if aim54_count == 6 and tank_count == 2 and total == 8:
            return 100.0, "NAVAIR 01-F14AAP-1 Figure 14-1: six AIM-54 plus two 267-gallon tanks"
        return None

    @property
    def model_drag_index(self) -> float:
        if self.is_clean:
            return 0.0
        reference = self.natops_drag_reference
        return reference[0] if reference is not None else self.provisional_drag_index

    @property
    def drag_data_valid(self) -> bool:
        return self.is_clean or self.natops_drag_reference is not None

    @property
    def recovery_model_drag_index(self) -> float:
        if all(disposition == "RETAIN" for disposition in self.recovery_dispositions.values()):
            return self.model_drag_index
        return self.recovery_provisional_drag_index

    @property
    def recovery_drag_data_valid(self) -> bool:
        return self.recovery_model_drag_index == 0.0 or (
            all(disposition == "RETAIN" for disposition in self.recovery_dispositions.values())
            and self.drag_data_valid
        )

    @property
    def has_nominal_weights(self) -> bool:
        return any(
            STORE_CATALOG[store_id].weight_source_class != "DIRECT"
            for store_id in self.stations.values()
            if store_id != EMPTY_STORE_ID
        )

    @property
    def has_unresolved_adapter_weights(self) -> bool:
        return any(
            STORE_CATALOG[store_id].adapter_weight_source_class == "UNRESOLVED_DCS_DELTA"
            for store_id in self.stations.values()
            if store_id != EMPTY_STORE_ID
        )

    @property
    def summary(self) -> str:
        counts = self.store_counts
        if not counts:
            return "Clean"
        return " + ".join(f"{count} x {STORE_CATALOG[key].label}" for key, count in counts.items())

    @property
    def compact_summary(self) -> str:
        if self.is_clean:
            return "CLEAN"
        return " / ".join(f"{count} {key}" for key, count in self.store_counts.items())

    @property
    def station_summary(self) -> str:
        loaded = [
            f"STA {station}: {station_option_label(station, store_id)}"
            for station, store_id in self.stations.items()
            if store_id != EMPTY_STORE_ID
        ]
        return "; ".join(loaded) if loaded else "Clean"

    @property
    def recovery_summary(self) -> str:
        entries = []
        for station, store_id in self.stations.items():
            if store_id == EMPTY_STORE_ID:
                continue
            entries.append(
                f"STA {station} {STORE_CATALOG[store_id].label}: {self.recovery_dispositions[station]}"
            )
        return "; ".join(entries) if entries else "Clean"


def loadout_from_preset(name: str, variant: str = "F-14B(U)") -> Loadout:
    if name not in LOADOUT_PRESETS:
        raise ValueError(f"Unknown loadout preset: {name}")
    return Loadout(dict(LOADOUT_PRESETS[name]), variant=variant)
