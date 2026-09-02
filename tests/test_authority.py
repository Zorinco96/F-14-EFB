from pathlib import Path

import pandas as pd

from src.f14perf.authority import authority_registry
from src.f14perf.data import DEFAULT_DATA_DIR


def test_every_major_domain_has_one_declared_production_authority():
    registry = authority_registry()
    assert {
        "aircraft_weight",
        "stores_inventory",
        "stores_weight",
        "stores_drag",
        "takeoff_thrust",
        "rpm_crosscheck",
        "takeoff_performance",
        "takeoff_trim",
        "climb",
        "cruise",
        "landing_approach",
        "landing_distance",
        "mission_fuel",
    } == registry.keys()
    assert registry["climb"].status == "PLANNING_HOLD"
    assert registry["cruise"].status == "PLANNING_HOLD"


def test_data_inventory_is_unique_and_covers_every_repository_data_file():
    inventory = pd.read_csv(DEFAULT_DATA_DIR / "data_inventory.csv")
    assert not inventory["path"].duplicated().any()
    inventoried = set(inventory["path"].astype(str))
    actual = {
        path.name
        for path in Path(DEFAULT_DATA_DIR).iterdir()
        if path.is_file() and path.suffix.lower() in {".csv", ".json"}
    }
    assert inventoried == actual
    assert not inventory["status"].isna().any()
