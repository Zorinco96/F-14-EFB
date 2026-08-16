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


def test_auto_uses_no_afterburner_and_respects_floor(data_dir):
    result = AutoTakeoffSelector(data_dir).select(baseline())
    assert result.flaps in {"UP", "MANEUVER", "FULL"}
    floors = {"UP": 85, "MANEUVER": 90, "FULL": 96}
    assert result.rpm_pct >= floors[result.flaps]
    assert result.rpm_pct <= 100


def test_full_auto_floor_is_96_percent(data_dir):
    result = AutoTakeoffSelector(data_dir).select(baseline(flaps="FULL"))
    assert result.feasible
    assert result.flaps == "FULL"
    assert result.rpm_pct == 96


def test_balanced_v1_below_vr(data_dir):
    result = TakeoffModel(data_dir).calculate(baseline(), "UP", 100)
    assert result.v1_kt < result.vr_kt
    assert result.v1_kt >= 0.84 * result.vr_kt - 1


def test_default_takeoff_wind_credit(data_dir):
    headwind = Environment(oat_c=15, qnh_inhg=29.92, wind_dir_deg=0, wind_speed_kt=20)
    result = TakeoffModel(data_dir).calculate(
        baseline(environment=headwind),
        "UP",
        100,
    )
    assert result.headwind_kt == 20
    assert result.credited_headwind_kt == 10


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
    assert result.thrust_setting == "REDUCED (90% RPM)"
    assert result.fuel_flow_pph_per_engine == 4800
    assert result.fuel_flow_pph_total == 9600
    assert result.vfs_kt == result.v2_kt + 20
    assert result.stabilizer_trim_anu == 3.0
    assert result.oei_climb_speed_kt == result.v2_kt + 15
    assert "before commencing the takeoff roll" in result.stabilizer_trim_note
    assert "gear up" in result.stabilizer_trim_note
    assert "MILITARY thrust on the operating engine" in result.stabilizer_trim_note


def test_pre_roll_trim_and_oei_speed_across_model_range(data_dir):
    model = TakeoffModel(data_dir)
    expected_trim = {"UP": 3.0, "MANEUVER": 6.0, "FULL": 0.0}
    for weight_lb in (40000, 65000, 76000):
        base = baseline()
        inputs = TakeoffInputs(weight_lb, base.environment, base.runway)
        for flaps in ("UP", "MANEUVER", "FULL"):
            result = model.calculate(inputs, flaps, 100)
            assert result.stabilizer_trim_anu == expected_trim[flaps]
            assert result.stabilizer_trim_band_anu == (
                (5.0, 7.0) if flaps == "MANEUVER" else None
            )
            assert result.oei_climb_speed_kt == result.v2_kt + 15
            assert "easy rotation at V2" in result.stabilizer_trim_note
