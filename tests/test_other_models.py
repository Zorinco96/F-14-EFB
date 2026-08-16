import pytest

from src.f14perf.climb import ClimbModel
from src.f14perf.cruise import CruiseModel
from src.f14perf.energy import EnergyModel
from src.f14perf.fuel import FuelModel
from src.f14perf.landing import LandingModel
from src.f14perf.mission import MissionPlanner
from src.f14perf.types import Environment, Runway, TakeoffInputs


def test_climb_schedule_caps_ias(data_dir):
    schedule = ClimbModel(data_dir).recommend_schedule(65000)
    assert len(schedule) == 10
    assert max(p.ias_kt for p in schedule) <= 250


def test_named_climb_profiles_are_distinct(data_dir):
    profiles = ClimbModel(data_dir).profiles(65000)
    efficient = profiles["MOST_EFFICIENT"]
    minimum_time = profiles["MINIMUM_TIME"]

    assert efficient.label == "Most Efficient"
    assert minimum_time.label == "Minimum Time (MIL)"
    assert len(efficient.points) == len(minimum_time.points) == 10
    assert efficient.altitude_gain_ft == minimum_time.altitude_gain_ft == 10000
    assert efficient.time_min > minimum_time.time_min > 0
    assert efficient.fuel_burn_lb > 0
    assert minimum_time.fuel_burn_lb > 0
    assert any(point.rpm_pct < 100 for point in efficient.points)
    assert all(point.rpm_pct == 100 for point in minimum_time.points)
    assert max(point.ias_kt for point in efficient.points + minimum_time.points) <= 250


def test_unknown_climb_strategy_is_rejected(data_dir):
    with pytest.raises(ValueError, match="MOST_EFFICIENT or MINIMUM_TIME"):
        ClimbModel(data_dir).recommend_schedule(65000, strategy="AB MAX")


def test_cruise_table_point(data_dir):
    c = CruiseModel(data_dir).optimum(65000, 0)
    assert c.optimum_altitude_ft == 33900
    assert c.optimum_mach == 0.718
    assert c.fuel_flow_pph_total > 0


def test_landing_table_point(data_dir):
    env = Environment(field_elevation_ft=0, oat_c=15, qnh_inhg=29.92)
    rwy = Runway(heading_deg=0, tora_ft=8000, toda_ft=8000, asda_ft=8000, elevation_ft=0)
    l = LandingModel(data_dir).calculate(54000, env, rwy)
    assert l.ground_roll_ft == 2800
    assert l.on_speed_aoa_units == 15


def test_energy_model_finite(data_dir):
    e = EnergyModel(data_dir).calculate(60000, 10000, 350)
    assert e.instantaneous_g >= 1
    assert e.sustained_g >= 1
    assert e.instantaneous_turn_rate_dps >= 0


def test_fuel_plan(data_dir):
    climb = ClimbModel(data_dir).recommend_schedule(65000)
    cruise = CruiseModel(data_dir).optimum(65000, 0)
    f = FuelModel().plan(16000, 100, climb, cruise, 4000, 2000)
    assert f.mission_burn_lb > 0
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
    card = MissionPlanner(data_dir).build_card(
        TakeoffInputs(65000, environment, runway),
        landing_weight_lb=54000,
        drag_index=0,
        route_nm=100,
        starting_fuel_lb=16000,
        bingo_lb=4000,
        joker_margin_lb=2000,
        climb_strategy="MINIMUM_TIME",
    )
    assert card.metadata["climb_strategy"] == "MINIMUM_TIME"
    assert card.metadata["climb_profile_label"] == "Minimum Time (MIL)"
    assert card.metadata["climb_time_to_10000_min"] > 0
    assert card.metadata["climb_fuel_to_10000_lb"] > 0
    assert all(point.rpm_pct == 100 for point in card.climb)
