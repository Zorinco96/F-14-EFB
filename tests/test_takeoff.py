import pytest

from src.f14perf.takeoff import AutoTakeoffSelector, TakeoffModel
from src.f14perf.types import Environment, Runway, TakeoffInputs


def baseline(environment=None, runway=None, **overrides):
    env = environment or Environment(field_elevation_ft=0, oat_c=15, qnh_inhg=29.92)
    rwy = runway or Runway(
        heading_deg=0,
        tora_ft=8000,
        toda_ft=8000,
        asda_ft=8000,
        elevation_ft=0,
    )
    return TakeoffInputs(65000, env, rwy, **overrides)


def test_legacy_baseline_table_points(data_dir):
    model = TakeoffModel(data_dir)
    up, _ = model._mil_table("UP", 65000, 0, 15)
    full, _ = model._mil_table("FULL", 65000, 0, 15)
    assert up["vr_kt"] == 159
    assert up["asd_ft"] == 2460
    assert up["agd_ft"] == 2900
    assert full["vr_kt"] == 140
    assert full["asd_ft"] == 2168
    assert full["agd_ft"] == 2550


def test_maneuver_calibration_anchor(data_dir):
    model = TakeoffModel(data_dir)
    man, prov = model._mil_table("MANEUVER", 65000, 0, 15)
    assert man["vr_kt"] == 146
    assert round(man["asd_ft"]) == 2583
    assert round(man["agd_ft"]) == 2456
    assert prov.method.value == "CALIBRATED"


def test_auto_uses_only_discrete_dry_ratings(data_dir):
    result = AutoTakeoffSelector(data_dir).select(baseline())
    assert result.flaps in {"UP", "MANEUVER", "FULL"}
    assert result.thrust_rating_id in {"DERATE_3", "DERATE_2", "DERATE_1", "MIL"}
    assert result.rpm_pct in {85, 90, 95, 100}
    assert result.auto_selected


def test_auto_selects_lowest_discrete_rating_that_clears_all_gates(data_dir):
    selector = AutoTakeoffSelector(data_dir)
    result = selector.select(baseline())
    lower = selector.model.calculate(baseline(), "UP", "DERATE 3")
    assert result.thrust_rating_id == "DERATE_2"
    assert result.feasible
    assert not lower.feasible
    assert lower.climb_gradient_ft_nm < baseline().climb_target_ft_nm


def test_full_auto_uses_mil_because_no_observed_high_derate_knot_exists(data_dir):
    result = AutoTakeoffSelector(data_dir).select(baseline(flaps="FULL"))
    assert result.feasible
    assert result.flaps == "FULL"
    assert result.thrust_rating_id == "MIL"
    assert result.rpm_pct == 100


def test_balanced_v1_below_vr(data_dir):
    result = TakeoffModel(data_dir).calculate(baseline(), "UP", 100)
    assert result.v1_kt < result.vr_kt
    assert result.v1_kt >= 0.84 * result.vr_kt - 1


def test_default_takeoff_wind_policy_uses_no_headwind_credit(data_dir):
    headwind = Environment(oat_c=15, qnh_inhg=29.92, wind_dir_deg=0, wind_speed_kt=20)
    result = TakeoffModel(data_dir).calculate(
        baseline(environment=headwind),
        "UP",
        100,
    )
    assert result.headwind_kt == 20
    assert result.credited_headwind_kt == 0


def test_tailwind_penalty_and_zero_headwind_option(data_dir):
    tailwind = Environment(oat_c=15, qnh_inhg=29.92, wind_dir_deg=180, wind_speed_kt=20)
    tailwind_result = TakeoffModel(data_dir).calculate(
        baseline(environment=tailwind),
        "UP",
        100,
    )
    assert tailwind_result.headwind_kt == -20
    assert tailwind_result.credited_headwind_kt == -30

    headwind = Environment(oat_c=15, qnh_inhg=29.92, wind_dir_deg=0, wind_speed_kt=20)
    no_credit_result = TakeoffModel(data_dir).calculate(
        baseline(environment=headwind, headwind_credit_pct=0),
        "UP",
        100,
    )
    assert no_credit_result.credited_headwind_kt == 0


def test_resolved_engine_guidance_and_pre_roll_trim_setting(data_dir):
    result = AutoTakeoffSelector(data_dir).select(
        baseline(thrust="MANUAL", rpm_pct=90)
    )
    assert result.thrust_setting == "DERATE 2"
    assert result.thrust_rating_id == "DERATE_2"
    assert result.eig_reference_rpm_pct == 90
    assert result.fuel_flow_pph_per_engine == 4800
    assert result.fuel_flow_pph_total == 9600
    assert result.vfs_kt == result.v2_kt + 20
    assert result.stabilizer_trim_anu == 5.5
    assert result.oei_climb_speed_kt == result.v2_kt + 15
    assert "before commencing the takeoff roll" in result.stabilizer_trim_note
    assert "gear up" in result.stabilizer_trim_note
    assert "MILITARY thrust on the operating engine" in result.stabilizer_trim_note


def test_military_command_uses_natops_on_deck_eig_reference(data_dir):
    result = TakeoffModel(data_dir).calculate(baseline(), "UP", 100)
    assert result.thrust_setting == "MIL"
    assert result.rpm_pct == 100
    assert result.eig_reference_rpm_pct == 100
    assert result.fuel_flow_pph_per_engine == 10100


def test_continuous_takeoff_rpm_is_rejected(data_dir):
    with pytest.raises(ValueError, match="Continuously variable takeoff RPM is disabled"):
        TakeoffModel(data_dir).calculate(baseline(), "UP", 92)


def test_discrete_rating_ff_breakpoints_are_data_backed(data_dir):
    model = TakeoffModel(data_dir)
    expected = {
        "DERATE 3": (85, 3400),
        "DERATE 2": (90, 4800),
        "DERATE 1": (95, 7000),
        "MIL": (100, 10100),
    }
    for rating, (rpm, ff) in expected.items():
        result = model.calculate(baseline(), "UP", rating)
        assert result.rpm_pct == rpm
        assert result.fuel_flow_pph_per_engine == ff


def test_ff_first_inverse_uses_henderson_anchor(data_dir):
    model = TakeoffModel(data_dir)
    point = model.engine.rpm_for_takeoff_ff(5_250, 2_492, 40)
    assert point.rpm_pct == 95
    assert point.fuel_flow_pph_per_engine == 5_250


def test_ff_first_inverse_uses_sea_level_anchor(data_dir):
    model = TakeoffModel(data_dir)
    point = model.engine.rpm_for_takeoff_ff(7_000, 0, 15)
    assert point.rpm_pct == 95
    assert point.fuel_flow_pph_per_engine == 7_000


def test_same_observed_rpm_has_materially_different_ff_between_environments(data_dir):
    model = TakeoffModel(data_dir)
    standard = model.engine.takeoff_rating("DERATE 1", 0, 15)
    henderson = model.engine.takeoff_rating("DERATE 1", 2_492, 40)
    assert standard.nominal_rpm_pct == henderson.nominal_rpm_pct == 95
    assert standard.fuel_flow_pph_per_engine == 7_000
    assert henderson.fuel_flow_pph_per_engine == 5_250
    assert henderson.fuel_flow_pph_per_engine / standard.fuel_flow_pph_per_engine == 0.75


def test_auto_uses_mil_when_reduced_rating_indications_are_unobserved(data_dir):
    environment = Environment(field_elevation_ft=4_000, oat_c=15, qnh_inhg=29.92)
    runway = Runway(tora_ft=12_000, toda_ft=12_000, asda_ft=12_000, elevation_ft=4_000)
    result = AutoTakeoffSelector(data_dir).select(
        baseline(environment=environment, runway=runway)
    )
    assert result.thrust_rating_id == "MIL"
    assert result.auto_selected


def test_pre_roll_trim_and_oei_speed_across_model_range(data_dir):
    model = TakeoffModel(data_dir)
    expected_trim = {"UP": 5.5, "MANEUVER": 7.0, "FULL": 0.0}
    expected_bands = {"UP": (5.0, 5.5), "MANEUVER": (6.5, 7.0), "FULL": None}
    for weight_lb in (40000, 65000, 76000):
        base = baseline()
        inputs = TakeoffInputs(weight_lb, base.environment, base.runway)
        for flaps in ("UP", "MANEUVER", "FULL"):
            result = model.calculate(inputs, flaps, 100)
            assert result.stabilizer_trim_anu == expected_trim[flaps]
            assert result.stabilizer_trim_band_anu == expected_bands[flaps]
            assert result.oei_climb_speed_kt == result.v2_kt + 15
            assert "easy rotation" in result.stabilizer_trim_note
            assert "next controlled DCS trial" in result.stabilizer_trim_note


def test_external_store_takeoff_is_marked_unvalidated(data_dir):
    result = TakeoffModel(data_dir).calculate(
        baseline(takeoff_loadout="STA 1A: AIM-9; STA 2: FPU-1 external tank; STA 7: FPU-1 external tank; STA 8A: AIM-9"),
        "MANEUVER",
        100,
    )
    assert not result.takeoff_data_valid
    assert "FPU-1 external tank" in result.takeoff_loadout
    assert any("External-store takeoff drag is not modeled" in w for w in result.warnings)


def test_hot_high_reduced_thrust_is_marked_unvalidated(data_dir):
    environment = Environment(field_elevation_ft=2492, oat_c=40, qnh_inhg=29.92)
    runway = Runway(
        heading_deg=0,
        tora_ft=8000,
        toda_ft=8000,
        asda_ft=8000,
        elevation_ft=2492,
    )
    result = TakeoffModel(data_dir).calculate(
        baseline(environment=environment, runway=runway),
        "UP",
        "DERATE 1",
    )
    assert not result.takeoff_data_valid
    assert any("Hot/high reduced-thrust" in w for w in result.warnings)


def test_hot_high_ff_guidance_uses_henderson_observations(data_dir):
    environment = Environment(field_elevation_ft=2492, oat_c=40, qnh_inhg=29.92)
    runway = Runway(
        heading_deg=353,
        tora_ft=6501,
        toda_ft=6501,
        asda_ft=6501,
        elevation_ft=2492,
    )
    model = TakeoffModel(data_dir)
    at_95 = model.calculate(
        baseline(environment=environment, runway=runway),
        "MANEUVER",
        "DERATE 1",
    )
    observed_98 = model.engine.takeoff_eig_reference(98, 2492, 40)
    sea_level = model.calculate(baseline(), "UP", "DERATE 1")
    assert at_95.fuel_flow_pph_per_engine == 5250
    assert observed_98.fuel_flow_pph_per_engine == 6000
    assert sea_level.fuel_flow_pph_per_engine == 7000
    assert "local indication only near PA 2492 ft / 40 C" in at_95.provenance.detail
