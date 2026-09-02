import pytest

from src.f14perf.aircraft import AircraftState
from src.f14perf.loadout import Loadout, loadout_from_preset


def test_aircraft_state_builds_one_launch_weight_from_configuration():
    loadout = loadout_from_preset("2 external tanks + 2 AIM-9", "F-14B(U)")
    aircraft = AircraftState("F-14B(U)", loadout, internal_fuel_lb=16_200, external_fuel_lb=3_600)
    assert aircraft.launch_zero_fuel_weight_lb == 41_780 + 440 + 1_580
    assert aircraft.launch_gross_weight_lb == 63_600
    assert aircraft.launch_fuel_capacity_lb == 19_800
    assert aircraft.launch_drag_index == 10


def test_fuel_and_store_changes_produce_new_stable_state_ids_and_weights():
    clean = AircraftState("F-14B", loadout_from_preset("Clean", "F-14B"), 10_000)
    fueled = AircraftState("F-14B", loadout_from_preset("Clean", "F-14B"), 12_000)
    armed = AircraftState("F-14B", loadout_from_preset("AAW01 | BFM (0/0/2)", "F-14B"), 10_000)
    assert fueled.launch_gross_weight_lb - clean.launch_gross_weight_lb == 2_000
    assert armed.launch_gross_weight_lb - clean.launch_gross_weight_lb == 380
    assert len({clean.config_id, fueled.config_id, armed.config_id}) == 3


def test_recovery_state_uses_dispositions_and_retained_fuel_capacity():
    loadout = Loadout(
        {"1A": "AIM9M", "2": "FPU1", "7": "FPU1"},
        variant="F-14B(U)",
        recovery_dispositions={"1A": "EXPEND", "2": "JETTISON"},
    )
    aircraft = AircraftState("F-14B(U)", loadout, 16_200, 3_600).with_recovery_fuel(18_000)
    assert aircraft.recovery_fuel_capacity_lb == 18_000
    assert aircraft.expected_recovery_fuel_lb == 18_000
    assert aircraft.recovery_zero_fuel_weight_lb == 41_780 + 440 + 600


def test_advanced_override_is_explicit_and_carried_into_recovery():
    loadout = loadout_from_preset("Clean", "F-14B")
    aircraft = AircraftState("F-14B", loadout, 16_200, gross_weight_override_lb=65_000)
    assert aircraft.launch_gross_weight_lb == 65_000
    assert aircraft.recovery_zero_fuel_weight_lb == aircraft.launch_zero_fuel_weight_lb
    assert any("override is active" in warning for warning in aircraft.warnings)


def test_aircraft_state_rejects_conflicting_variant_and_excess_fuel():
    with pytest.raises(ValueError, match="variant must match"):
        AircraftState("F-14B", loadout_from_preset("Clean", "F-14B(U)"), 10_000)
    with pytest.raises(ValueError, match="Internal fuel exceeds"):
        AircraftState("F-14B", loadout_from_preset("Clean", "F-14B"), 17_000)
