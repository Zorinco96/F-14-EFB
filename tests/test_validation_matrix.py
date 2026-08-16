"""Operational regression gates for the audited planning envelope."""

from src.f14perf.landing import LandingModel
from src.f14perf.takeoff import TakeoffModel
from src.f14perf.types import Environment, Runway, TakeoffInputs


def _takeoff(
    weight_lb=65_000,
    elevation_ft=0,
    oat_c=15,
    qnh_inhg=29.92,
    wind_dir_deg=None,
    wind_speed_kt=0,
    condition="DRY",
    runway_ft=8_000,
    flaps="UP",
    rpm_pct=100,
    loadout="Clean",
):
    environment = Environment(
        field_elevation_ft=elevation_ft,
        oat_c=oat_c,
        qnh_inhg=qnh_inhg,
        wind_dir_deg=wind_dir_deg,
        wind_speed_kt=wind_speed_kt,
    )
    runway = Runway(
        heading_deg=0,
        tora_ft=runway_ft,
        toda_ft=runway_ft,
        asda_ft=runway_ft,
        elevation_ft=elevation_ft,
        condition=condition,
    )
    inputs = TakeoffInputs(
        weight_lb,
        environment,
        runway,
        flaps=flaps,
        thrust="MANUAL",
        rpm_pct=rpm_pct,
        takeoff_loadout=loadout,
    )
    return TakeoffModel().calculate(inputs, flaps, rpm_pct)


def test_natops_mil_engine_indication_anchor():
    result = _takeoff()
    assert result.fuel_flow_pph_per_engine == 10_100
    assert result.thrust_setting == "MIL"


def test_temperature_weight_and_surface_trends_are_conservative():
    light = _takeoff(weight_lb=58_000)
    heavy = _takeoff(weight_lb=72_000)
    standard = _takeoff()
    hot = _takeoff(oat_c=49)
    tailwind = _takeoff(wind_dir_deg=180, wind_speed_kt=10)
    wet = _takeoff(condition="WET")

    assert heavy.vr_kt > light.vr_kt
    assert heavy.factored_agd_ft > light.factored_agd_ft
    assert hot.factored_agd_ft > standard.factored_agd_ft
    assert tailwind.factored_agd_ft > standard.factored_agd_ft
    assert wet.factored_agd_ft > standard.factored_agd_ft
    assert wet.factored_asd_ft > standard.factored_asd_ft


def test_cold_light_and_hot_high_heavy_extrapolations_fail_closed():
    cold_light = _takeoff(weight_lb=45_000, oat_c=-10)
    hot_high_heavy = _takeoff(
        weight_lb=75_000,
        elevation_ft=5_000,
        oat_c=35,
        runway_ft=10_000,
    )
    assert not cold_light.takeoff_data_valid
    assert not hot_high_heavy.takeoff_data_valid
    assert any("outside the legacy takeoff grid" in note for note in cold_light.warnings)
    assert any("outside the legacy takeoff grid" in note for note in hot_high_heavy.warnings)


def test_henderson_correlated_tacview_sequence_is_close_but_held():
    result = _takeoff(
        weight_lb=62_000,
        elevation_ft=2_492,
        oat_c=40,
        runway_ft=4_800,
        flaps="MANEUVER",
        rpm_pct=95,
        loadout="2 external tanks + 2 AIM-9",
    )
    tacview_liftoff_ft = 4_853
    relative_error = abs(result.agd_ft - tacview_liftoff_ft) / tacview_liftoff_ft

    assert relative_error < 0.10
    assert result.factored_agd_ft > 4_800
    assert not result.takeoff_data_valid
    assert not result.feasible


def test_natops_figure_11_8_on_speed_anchor():
    environment = Environment(field_elevation_ft=0, oat_c=15, qnh_inhg=29.92)
    runway = Runway(tora_ft=8_000, toda_ft=8_000, asda_ft=8_000, elevation_ft=0)
    result = LandingModel().calculate(54_000, environment, runway)
    assert result.on_speed_aoa_units == 15
    assert result.on_speed_ias_est_kt == 139.7
    assert result.on_speed_ias_dlc_stowed_kt == 130.6
    assert result.on_speed_ias_tolerance_kt == 4.0
