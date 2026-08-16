from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StoreDefinition:
    label: str
    model_drag_units: float


STORE_CATALOG = {
    "EMPTY": StoreDefinition("Empty", 0.0),
    "AIM9": StoreDefinition("AIM-9", 1.0),
    "AIM9L": StoreDefinition("AIM-9L", 1.0),
    "AIM9M": StoreDefinition("AIM-9M", 1.0),
    "AIM7F": StoreDefinition("AIM-7F", 2.0),
    "AIM7M": StoreDefinition("AIM-7M", 2.0),
    "AIM54A47": StoreDefinition("AIM-54A Mk 47", 4.0),
    "AIM54A60": StoreDefinition("AIM-54A Mk 60", 4.0),
    "AIM54C47": StoreDefinition("AIM-54C Mk 47", 4.0),
    "FPU1": StoreDefinition("FPU-1 external tank", 4.0),
    "LANTIRN": StoreDefinition("LANTIRN pod", 3.0),
    "TARPS": StoreDefinition("TARPS pod", 6.0),
    "ALQ167": StoreDefinition("ALQ-167 pod", 3.0),
    "TCTS": StoreDefinition("TCTS pod", 1.0),
    "LAU138": StoreDefinition("LAU-138 chaff adapter", 0.5),
    "SMOKE": StoreDefinition("Smokewinder", 1.0),
    "OTHER_AG": StoreDefinition("Other air-to-ground store/rack", 4.0),
}


STATION_OPTIONS = {
    "1A": ("EMPTY", "AIM9", "AIM9L", "AIM9M", "LAU138", "SMOKE", "TCTS"),
    "1B": (
        "EMPTY", "AIM9", "AIM9L", "AIM9M", "AIM7F", "AIM7M",
        "AIM54A47", "AIM54A60", "AIM54C47", "TCTS", "OTHER_AG",
    ),
    "2": ("EMPTY", "FPU1"),
    "3": ("EMPTY", "AIM7F", "AIM7M", "AIM54A47", "AIM54A60", "AIM54C47", "OTHER_AG"),
    "4": ("EMPTY", "AIM7F", "AIM7M", "AIM54A47", "AIM54A60", "AIM54C47", "OTHER_AG"),
    "5": ("EMPTY", "AIM7F", "AIM7M", "AIM54A47", "AIM54A60", "AIM54C47", "TARPS", "OTHER_AG"),
    "6": ("EMPTY", "AIM7F", "AIM7M", "AIM54A47", "AIM54A60", "AIM54C47", "ALQ167", "OTHER_AG"),
    "7": ("EMPTY", "FPU1"),
    "8B": (
        "EMPTY", "AIM9", "AIM9L", "AIM9M", "AIM7F", "AIM7M",
        "AIM54A47", "AIM54A60", "AIM54C47", "LANTIRN", "TCTS", "OTHER_AG",
    ),
    "8A": ("EMPTY", "AIM9", "AIM9L", "AIM9M", "LAU138", "SMOKE", "TCTS"),
}


LOADOUT_PRESETS = {
    "Clean": {},
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
