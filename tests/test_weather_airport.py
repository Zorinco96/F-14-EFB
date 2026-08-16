import pytest

from src.f14perf.airport import AirportDatabase
from src.f14perf.atmosphere import atmosphere, cas_to_mach, mach_to_cas_kt
from src.f14perf.weather import parse_metar, wind_components


def test_metar_parser():
    p = parse_metar("KLSV 152355Z 22012G20KT 10SM FEW100 35/08 A2985", 2000)
    assert p.environment.oat_c == 35
    assert abs(p.environment.qnh_inhg - 29.85) < 0.001
    assert p.environment.wind_dir_deg == 220
    assert p.environment.wind_speed_kt == 12
    assert p.environment.wind_gust_kt == 20


def test_wind_component():
    hw, xw = wind_components(90, 20, 90)
    assert round(hw) == 20
    assert round(xw) == 0


def test_airport_slope_derivation(data_dir):
    db = AirportDatabase(data_dir)
    r = db.get("Test", "Field", "09").runway
    assert round(r.slope_pct, 3) == 0.25
    assert r.toda_ft == 8200
    assert r.asda_ft == 8100


def test_henderson_35l_is_available_in_production_database():
    db = AirportDatabase()
    r = db.get("Nevada", "Henderson Executive", "35L").runway
    assert r.tora_ft == 6501
    assert r.heading_deg == 353
    assert r.elevation_ft == 2492


def test_compressible_kias_mach_round_trip():
    atm = atmosphere(34000)
    kias = mach_to_cas_kt(0.718, atm["pressure_pa"])
    assert 240 < kias < 270
    assert cas_to_mach(kias, atm["pressure_pa"]) == pytest.approx(0.718, abs=0.001)
