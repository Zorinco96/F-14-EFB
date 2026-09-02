import pytest

from src.f14perf.aircraft import AircraftState
from src.f14perf.climb import ClimbModel
from src.f14perf.cruise import CruiseModel
from src.f14perf.energy import EnergyModel
from src.f14perf.fuel import FuelModel
from src.f14perf.kneeboard import render_kneeboard_png, render_mission_card_pdf
from src.f14perf.landing import LandingModel
from src.f14perf.mission import MissionPlanner
from src.f14perf.loadout import loadout_from_preset
from src.f14perf.types import Environment, Runway, TakeoffInputs


def test_climb_schedule_caps_ias(data_dir):
    schedule = ClimbModel(data_dir).recommend_schedule(65000)
    assert len(schedule) == 10
    assert max(p.ias_kt for p in schedule) <= 250


def test_named_climb_profiles_are_distinct(data_dir):
    profiles = ClimbModel(data_dir).profiles(65000)
    efficient = profiles["MOST_EFFICIENT"]
    minimum_time = profiles["MINIMUM_TIME"]

    assert efficient.label == "Conservative dry planning"
    assert minimum_time.label == "MIL climb planning"
    assert len(efficient.points) == len(minimum_time.points) == 10
    assert efficient.altitude_gain_ft == minimum_time.altitude_gain_ft == 10000
    assert efficient.time_min > minimum_time.time_min > 0
    assert efficient.fuel_burn_lb > 0
    assert minimum_time.fuel_burn_lb > 0
    assert efficient.distance_nm > 0
    assert minimum_time.distance_nm > 0
    assert any(point.rpm_pct < 100 for point in efficient.points)
    assert all(point.rpm_pct == 100 for point in minimum_time.points)
    assert max(point.ias_kt for point in efficient.points + minimum_time.points) <= 250
    assert max(point.roc_fpm for point in efficient.points + minimum_time.points) <= 3500
    assert all(point.fuel_flow_pph_per_engine > 0 for point in efficient.points)


def test_unknown_climb_strategy_is_rejected(data_dir):
    with pytest.raises(ValueError, match="MOST_EFFICIENT or MINIMUM_TIME"):
        ClimbModel(data_dir).recommend_schedule(65000, strategy="AB MAX")


def test_cruise_table_point(data_dir):
    c = CruiseModel(data_dir).optimum(65000, 0)
    assert c.optimum_altitude_ft == 34000
    assert c.flight_level == 340
    assert c.optimum_mach == 0.72
    assert c.optimum_ias_kt > 0
    assert c.rpm_pct > 0
    assert c.rpm_pct % 5 == 0
    assert c.fuel_flow_pph_per_engine > 0
    assert c.fuel_flow_pph_per_engine % 250 == 0
    assert c.fuel_flow_pph_total == c.fuel_flow_pph_per_engine * 2


def test_landing_table_point(data_dir):
    env = Environment(field_elevation_ft=0, oat_c=15, qnh_inhg=29.92)
    rwy = Runway(heading_deg=0, tora_ft=8000, toda_ft=8000, asda_ft=8000, elevation_ft=0)
    l = LandingModel(data_dir).calculate(54000, env, rwy)
    assert l.ground_roll_ft == 2800
    assert l.on_speed_aoa_units == 15
    assert l.on_speed_ias_est_kt == 139.7
    assert l.on_speed_ias_dlc_stowed_kt == 130.6
    assert l.on_speed_ias_tolerance_kt == 4.0


def test_energy_model_finite(data_dir):
    e = EnergyModel(data_dir).calculate(60000, 10000, 350)
    assert e.planning_g >= 1
    assert e.turn_rate_dps > 0
    assert e.turn_radius_ft > 0
    assert e.turn_360_sec == pytest.approx(e.turn_180_sec * 2, abs=0.2)


def test_fuel_plan(data_dir):
    climb = ClimbModel(data_dir).recommend_schedule(65000)
    cruise = CruiseModel(data_dir).optimum(65000, 0)
    f = FuelModel().plan(16000, 100, climb, cruise, 4000, 2000)
    assert f.mission_burn_lb > 0
    assert f.mission_burn_lb % 500 == 0
    assert f.landing_fuel_lb < f.starting_fuel_lb


def test_mission_card_retains_selected_climb_strategy(data_dir):
    environment = Environment(field_elevation_ft=0, oat_c=15, qnh_inhg=29.92)
    runway = Runway(
        heading_deg=0,
        tora_ft=8000,
        toda_ft=8000,
        asda_ft=8000,
        elevation_ft=0,
    )
    aircraft = AircraftState(
        "F-14B",
        loadout_from_preset("Clean", "F-14B"),
        internal_fuel_lb=16_000,
        gross_weight_override_lb=65_000,
    )
    card = MissionPlanner(data_dir).build_for_aircraft(
        aircraft,
        environment,
        runway,
        route_nm=100,
        bingo_lb=4000,
        joker_margin_lb=2000,
        climb_strategy="MINIMUM_TIME",
    )
    assert card.metadata["climb_strategy"] == "MINIMUM_TIME"
    assert card.metadata["climb_profile_label"] == "MIL climb planning"
    assert card.metadata["climb_time_to_cruise_min"] > 0
    assert card.metadata["climb_fuel_to_cruise_lb"] > 0
    assert card.metadata["climb_distance_to_cruise_nm"] > 0
    assert all(point.rpm_pct == 100 for point in card.climb)
    assert card.climb[-1].altitude_ft == card.cruise.optimum_altitude_ft
    assert card.metadata["launch_gross_weight_lb"] == 65_000
    assert card.metadata["aircraft_state_id"]


def test_independent_mission_phase_inputs_are_disabled(data_dir):
    with pytest.raises(RuntimeError, match="Independent takeoff"):
        MissionPlanner(data_dir).build_card()


def test_landing_fuel_reference_is_rounded_down_and_conservative(data_dir):
    reference = LandingModel(data_dir).fuel_reference(
        takeoff_weight_lb=62000,
        starting_fuel_lb=16000,
        expendable_credit_lb=370,
    )
    assert reference.field_retained_fuel_lb == 14000
    assert reference.carrier_retained_fuel_lb == 8000
    assert reference.field_expended_fuel_lb == 14300
    assert reference.carrier_expended_fuel_lb == 8300


def test_kneeboard_renderer_returns_dcs_sized_png():
    payload = render_kneeboard_png(
        "vTF-77 Test",
        "F-14B(U)",
        [("Takeoff", ["V1 140 | VR 150 | V2 160", "TRIM 6.0 ANU"])],
    )
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(payload) > 1000


def test_mission_card_renderer_returns_one_page_pdf():
    payload = render_mission_card_pdf(
        "vTF-77 Test",
        "F-14B(U)",
        [("Takeoff", ["V1 WITHHELD | VR 150 | V2 160", "SET 7,000 PPH/ENG"])],
    )
    assert payload.startswith(b"%PDF-")
    assert len(payload) > 1000
