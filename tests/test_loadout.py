import pytest

from src.f14perf.loadout import (
    STATION_ORDER,
    STORE_CATALOG,
    Loadout,
    loadout_from_preset,
    station_options,
)


def test_store_catalog_is_structured_and_complete_for_heatblur_matrix():
    assert len(STORE_CATALOG) == 38  # 37 DCS entries plus explicit EMPTY
    assert {"AIM9L", "AIM9M", "AIM7E2", "AIM7F", "AIM7M"} <= STORE_CATALOG.keys()
    assert {"AIM54A47", "AIM54A60", "AIM54C47"} <= STORE_CATALOG.keys()
    assert {"GBU24E", "GBU31V2", "GBU31V4", "GBU38", "TARPS", "LANTIRN"} <= STORE_CATALOG.keys()


@pytest.mark.parametrize(
    ("store_id", "quantities"),
    [
        ("AIM9M", (1, 1, 0, 0, 0, 0, 0, 0, 1, 1)),
        ("AIM7M", (0, 1, 0, 1, 1, 1, 1, 0, 1, 0)),
        ("AIM54C47", (0, 1, 0, 1, 1, 1, 1, 0, 1, 0)),
        ("MK82", (0, 2, 0, 4, 3, 3, 4, 0, 2, 0)),
        ("MK83", (0, 1, 0, 3, 1, 1, 3, 0, 1, 0)),
        ("MK84", (0, 0, 0, 1, 1, 1, 1, 0, 0, 0)),
        ("MK20", (0, 2, 0, 2, 1, 1, 2, 0, 2, 0)),
        ("GBU10", (0, 0, 0, 1, 0, 0, 1, 0, 0, 0)),
        ("GBU12", (0, 0, 0, 1, 1, 1, 1, 0, 0, 0)),
        ("GBU24", (0, 0, 0, 1, 0, 1, 0, 0, 0, 0)),
        ("BDU33", (0, 3, 0, 4, 3, 3, 4, 0, 3, 0)),
        ("LAU10", (0, 2, 0, 2, 0, 0, 1, 0, 2, 0)),
        ("SUU25", (0, 0, 0, 0, 2, 1, 0, 0, 0, 0)),
        ("FPU1", (0, 0, 1, 0, 0, 0, 0, 1, 0, 0)),
    ],
)
def test_heatblur_station_matrix_quantities(store_id, quantities):
    store = STORE_CATALOG[store_id]
    assert tuple(store.quantity_for(station) for station in STATION_ORDER) == quantities


def test_clean_preset_has_no_drag_or_weight():
    loadout = loadout_from_preset("Clean")
    assert loadout.is_clean
    assert loadout.model_drag_index == 0
    assert loadout.launch_payload_weight_lb == 0
    assert loadout.summary == "Clean"


def test_two_tanks_two_aim9_preset_integrates_weight_fuel_and_drag():
    loadout = loadout_from_preset("2 external tanks + 2 AIM-9")
    assert loadout.normalized_stations["1A"] == "AIM9M"
    assert loadout.normalized_stations["2"] == "FPU1"
    assert loadout.normalized_stations["7"] == "FPU1"
    assert loadout.normalized_stations["8A"] == "AIM9M"
    assert loadout.loaded_store_count == 4
    assert loadout.launch_payload_weight_lb == 1_580
    assert loadout.external_fuel_capacity_lb == 3_600
    assert loadout.model_drag_index == 10
    assert not loadout.drag_data_valid


def test_station_store_and_variant_compatibility_are_enforced():
    with pytest.raises(ValueError, match="not supported"):
        Loadout({"2": "AIM9M"})
    assert "GBU31V2" in station_options("3", "F-14B(U)")
    assert "GBU31V2" not in station_options("3", "F-14B")
    with pytest.raises(ValueError, match="not supported"):
        Loadout({"3": "GBU31V2"}, variant="F-14B")


def test_aft_phoenix_requires_corresponding_forward_pallet():
    with pytest.raises(ValueError, match="requires a forward Phoenix pallet"):
        Loadout({"4": "AIM54C47"})
    loadout = Loadout({"3": "PHX_PALLET_EMPTY", "4": "AIM54C47"})
    assert loadout.normalized_stations["3"] == "PHX_PALLET_EMPTY"


def test_explicit_empty_and_asymmetric_configurations_are_supported():
    loadout = Loadout({"1A": "EMPTY", "8A": "AIM9M"})
    assert loadout.normalized_stations["1A"] == "EMPTY"
    assert loadout.store_counts == {"AIM9M": 1}


def test_recovery_disposition_removes_store_mass_and_tank_capacity():
    loadout = Loadout(
        {"1A": "AIM9M", "2": "FPU1", "7": "FPU1"},
        recovery_dispositions={"1A": "EXPEND", "2": "JETTISON"},
    )
    assert loadout.launch_payload_weight_lb == 1_390
    assert loadout.recovery_payload_weight_lb == 600
    assert loadout.planned_removed_weight_lb == 790
    assert loadout.external_fuel_capacity_lb == 3_600
    assert loadout.recovery_external_fuel_capacity_lb == 1_800


def test_heatblur_scl_presets_map_to_store_quantities():
    heavy_cap = loadout_from_preset("AAW05 | Heavy CAP (4/2/2)")
    counts = heavy_cap.store_counts
    assert counts["AIM54C47"] == 4
    assert counts["AIM7M"] == 2
    assert counts["AIM9M"] == 2


def test_natops_figure_14_1_drag_reference_is_not_generalized():
    reference = loadout_from_preset("Fleet defense | 6 AIM-54 + 2 tanks")
    assert reference.natops_drag_reference is not None
    assert reference.natops_drag_reference[0] == 100
    assert reference.drag_data_valid
    assert loadout_from_preset("AAW06 | Six Shooter (6/0/2)").natops_drag_reference is None
