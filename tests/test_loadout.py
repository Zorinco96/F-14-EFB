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


def test_station_store_compatibility_is_enforced():
    with pytest.raises(ValueError, match="not supported"):
        Loadout({"2": "AIM9"})
