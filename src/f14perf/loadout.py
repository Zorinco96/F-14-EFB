from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StoreDefinition:
    label: str
    model_drag_units: float
    expendable_credit_lb: float = 0.0


STORE_CATALOG = {
    "EMPTY": StoreDefinition("Empty", 0.0),
    # Credits are deliberately rounded down from nominal loaded-store weights.
    # This keeps the all-expendables-expended landing-fuel reference cautious.
    "AIM9": StoreDefinition("AIM-9", 1.0, 185.0),
    "AIM9L": StoreDefinition("AIM-9L", 1.0, 185.0),
    "AIM9M": StoreDefinition("AIM-9M", 1.0, 185.0),
    "AIM7F": StoreDefinition("AIM-7F", 2.0, 500.0),
    "AIM7M": StoreDefinition("AIM-7M", 2.0, 500.0),
    "AIM54A47": StoreDefinition("AIM-54A Mk 47", 4.0, 985.0),
    "AIM54A60": StoreDefinition("AIM-54A Mk 60", 4.0, 985.0),
    "AIM54C47": StoreDefinition("AIM-54C Mk 47", 4.0, 985.0),
    "FPU1": StoreDefinition("FPU-1 external tank", 4.0),
    "LANTIRN": StoreDefinition("LANTIRN pod", 3.0),
    "TARPS": StoreDefinition("TARPS pod", 6.0),
    "ALQ167": StoreDefinition("ALQ-167 pod", 3.0),
    "TCTS": StoreDefinition("TCTS pod", 1.0),
    "LAU138": StoreDefinition("LAU-138 chaff adapter", 0.5),
    "SMOKE": StoreDefinition("Smokewinder", 1.0),
    "MK82": StoreDefinition("Mk-82", 2.0, 500.0),
    "MK83": StoreDefinition("Mk-83", 3.0, 1_000.0),
    "MK84": StoreDefinition("Mk-84", 4.0, 2_000.0),
    "GBU10": StoreDefinition("GBU-10", 5.0, 2_000.0),
    "GBU12": StoreDefinition("GBU-12", 3.0, 550.0),
    "GBU16": StoreDefinition("GBU-16", 4.0, 1_000.0),
    "GBU24": StoreDefinition("GBU-24E/B", 6.0, 2_000.0),
    "GBU31": StoreDefinition("GBU-31", 5.0, 2_000.0),
    "GBU38": StoreDefinition("GBU-38", 3.0, 500.0),
    "CBU99": StoreDefinition("Mk-20 Rockeye / CBU-99", 3.0, 490.0),
    "OTHER_AG": StoreDefinition("Other air-to-ground store/rack", 4.0),
}


TUNNEL_AG_OPTIONS = (
    "MK82", "MK83", "MK84", "GBU10", "GBU12", "GBU16", "GBU24",
    "GBU31", "GBU38", "CBU99", "OTHER_AG",
)


STATION_OPTIONS = {
    "1A": ("EMPTY", "AIM9", "AIM9L", "AIM9M", "LAU138", "SMOKE", "TCTS"),
    "1B": (
        "EMPTY", "AIM9", "AIM9L", "AIM9M", "AIM7F", "AIM7M",
        "AIM54A47", "AIM54A60", "AIM54C47", "TCTS", "OTHER_AG",
    ),
    "2": ("EMPTY", "FPU1"),
    "3": ("EMPTY", "AIM7F", "AIM7M", "AIM54A47", "AIM54A60", "AIM54C47", *TUNNEL_AG_OPTIONS),
    "4": ("EMPTY", "AIM7F", "AIM7M", "AIM54A47", "AIM54A60", "AIM54C47", *TUNNEL_AG_OPTIONS),
    "5": ("EMPTY", "AIM7F", "AIM7M", "AIM54A47", "AIM54A60", "AIM54C47", "TARPS", *TUNNEL_AG_OPTIONS),
    "6": ("EMPTY", "AIM7F", "AIM7M", "AIM54A47", "AIM54A60", "AIM54C47", "ALQ167", *TUNNEL_AG_OPTIONS),
    "7": ("EMPTY", "FPU1"),
    "8B": (
        "EMPTY", "AIM9", "AIM9L", "AIM9M", "AIM7F", "AIM7M",
        "AIM54A47", "AIM54A60", "AIM54C47", "LANTIRN", "TCTS", "OTHER_AG",
    ),
    "8A": ("EMPTY", "AIM9", "AIM9L", "AIM9M", "LAU138", "SMOKE", "TCTS"),
}


LOADOUT_PRESETS = {
    "Clean": {},
    "AAW01 | BFM (0/0/2)": {
        "1A": "AIM9M",
        "8A": "AIM9M",
    },
    "AAW05 | Heavy CAP (4/2/2)": {
        "1A": "AIM9M",
        "1B": "AIM7M",
        "3": "AIM54C47",
        "4": "AIM54C47",
        "5": "AIM54C47",
        "6": "AIM54C47",
        "8B": "AIM7M",
        "8A": "AIM9M",
    },
    "AAW06 | Six Shooter (6/0/2)": {
        "1A": "AIM9M",
        "1B": "AIM54C47",
        "3": "AIM54C47",
        "4": "AIM54C47",
        "5": "AIM54C47",
        "6": "AIM54C47",
        "8B": "AIM54C47",
        "8A": "AIM9M",
    },
    "AG04 | Medium Strike": {
        "1A": "AIM9M",
        "1B": "AIM54C47",
        "3": "GBU31",
        "6": "GBU31",
        "8A": "AIM9M",
    },
    "TARPS01 | TARPS": {
        "1A": "AIM9M",
        "1B": "AIM7M",
        "5": "TARPS",
        "8B": "AIM7M",
        "8A": "AIM9M",
    },
    "Fleet defense | 6 AIM-54 + 2 tanks": {
        "1B": "AIM54C47",
        "2": "FPU1",
        "3": "AIM54C47",
        "4": "AIM54C47",
        "5": "AIM54C47",
        "6": "AIM54C47",
        "7": "FPU1",
        "8B": "AIM54C47",
    },
    "2 external tanks + 2 AIM-9": {
        "1A": "AIM9",
        "2": "FPU1",
        "7": "FPU1",
        "8A": "AIM9",
    },
}


@dataclass(frozen=True)
class Loadout:
    stations: dict[str, str]

    def __post_init__(self) -> None:
        for station, store_key in self.stations.items():
            if station not in STATION_OPTIONS:
                raise ValueError(f"Unsupported F-14 station: {station}")
            if store_key not in STATION_OPTIONS[station]:
                raise ValueError(f"{store_key} is not supported on F-14 station {station}")

    @property
    def is_clean(self) -> bool:
        return all(store == "EMPTY" for store in self.normalized_stations.values())

    @property
    def normalized_stations(self) -> dict[str, str]:
        return {station: self.stations.get(station, "EMPTY") for station in STATION_OPTIONS}

    @property
    def model_drag_index(self) -> float:
        return sum(
            STORE_CATALOG[store].model_drag_units
            for store in self.normalized_stations.values()
        )

    @property
    def expendable_credit_weight_lb(self) -> float:
        return sum(
            STORE_CATALOG[store].expendable_credit_lb
            for store in self.normalized_stations.values()
        )

    @property
    def loaded_store_count(self) -> int:
        return sum(store != "EMPTY" for store in self.normalized_stations.values())

    @property
    def store_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for store in self.normalized_stations.values():
            if store != "EMPTY":
                counts[store] = counts.get(store, 0) + 1
        return counts

    @property
    def natops_drag_reference(self) -> tuple[float, str] | None:
        """Return only the two configurations explicitly printed in Figure 14-1."""

        counts = self.store_counts
        aim7_count = sum(counts.get(key, 0) for key in ("AIM7F", "AIM7M"))
        aim54_count = sum(
            counts.get(key, 0) for key in ("AIM54A47", "AIM54A60", "AIM54C47")
        )
        tank_count = counts.get("FPU1", 0)
        total = sum(counts.values())
        if aim7_count == 4 and total == 4:
            return 8.0, "NAVAIR 01-F14AAP-1 Figure 14-1: four AIM-7"
        if aim54_count == 6 and tank_count == 2 and total == 8:
            return 100.0, "NAVAIR 01-F14AAP-1 Figure 14-1: six AIM-54 plus two 267-gallon tanks"
        return None

    @property
    def summary(self) -> str:
        loaded = [
            f"STA {station}: {STORE_CATALOG[store].label}"
            for station, store in self.normalized_stations.items()
            if store != "EMPTY"
        ]
        return "; ".join(loaded) if loaded else "Clean"


def loadout_from_preset(name: str) -> Loadout:
    if name not in LOADOUT_PRESETS:
        raise ValueError(f"Unknown loadout preset: {name}")
    return Loadout(dict(LOADOUT_PRESETS[name]))
