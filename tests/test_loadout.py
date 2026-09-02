import pytest

from src.f14perf.loadout import Loadout, loadout_from_preset


def test_clean_preset_has_no_drag_units():
    loadout = loadout_from_preset("Clean")
    assert loadout.is_clean
    assert loadout.model_drag_index == 0
    assert loadout.summary == "Clean"


def test_two_tanks_two_aim9_preset_matches_dcs_stations():
    loadout = loadout_from_preset("2 external tanks + 2 AIM-9")
    assert not loadout.is_clean
    assert loadout.normalized_stations["1A"] == "AIM9"
    assert loadout.normalized_stations["2"] == "FPU1"
    assert loadout.normalized_stations["7"] == "FPU1"
    assert loadout.normalized_stations["8A"] == "AIM9"
    assert loadout.model_drag_index == 10
    assert loadout.expendable_credit_weight_lb == 370


def test_station_store_compatibility_is_enforced():
    with pytest.raises(ValueError, match="not supported"):
        Loadout({"2": "AIM9"})


def test_heatblur_scl_presets_map_to_station_counts():
    heavy_cap = loadout_from_preset("AAW05 | Heavy CAP (4/2/2)")
    counts = heavy_cap.store_counts
    assert counts["AIM54C47"] == 4
    assert counts["AIM7M"] == 2
    assert counts["AIM9M"] == 2


def test_natops_figure_14_1_drag_reference_is_not_generalized():
    reference = loadout_from_preset("Fleet defense | 6 AIM-54 + 2 tanks")
    assert reference.natops_drag_reference is not None
    assert reference.natops_drag_reference[0] == 100
    assert loadout_from_preset("AAW06 | Six Shooter (6/0/2)").natops_drag_reference is None
