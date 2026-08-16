from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    takeoff_rows = []
    for flap, vs, v1, vr, v2, asd, agd, note in [
        (0, 125, 150, 159, 172, 2460, 2900, "NATOPS-UP"),
        (40, 120, 131, 140, 153, 2168, 2550, "NATOPS-FULL"),
    ]:
        takeoff_rows.append({
            "model": "F-14B", "flap_deg": flap, "thrust": "MILITARY",
            "gw_lbs": 65000, "press_alt_ft": 0, "oat_c": 15,
            "Vs_kt": vs, "V1_kt": v1, "Vr_kt": vr, "V2_kt": v2,
            "ASD_ft": asd, "AGD_ft": agd, "note": note,
        })
    pd.DataFrame(takeoff_rows).to_csv(tmp_path / "f14_perf.csv", index=False)
    pd.DataFrame([
        {"weight": 55000, "v1": 110, "vr": 120, "v2": 130, "vfs": 150},
        {"weight": 65000, "v1": 120, "vr": 130, "v2": 140, "vfs": 160},
        {"weight": 75000, "v1": 130, "vr": 140, "v2": 150, "vfs": 170},
    ]).to_csv(tmp_path / "vspeeds.csv", index=False)

    engine_rows = [
        {"altitude_ft": 0, "mach": 0.2, "thrust_type": "IDLE", "thrust_lbf": 3000, "ff_pph": 1700},
        {"altitude_ft": 0, "mach": 0.2, "thrust_type": "MIL", "thrust_lbf": 27000, "ff_pph": 11000},
        {"altitude_ft": 0, "mach": 0.2, "thrust_type": "AB", "thrust_lbf": 30200, "ff_pph": 18000},
    ]
    pd.DataFrame(engine_rows).to_csv(tmp_path / "F110_engine.csv", index=False)
    pd.DataFrame([
        {"FF_pph": 1200, "RPM_pct": 71},
        {"FF_pph": 2500, "RPM_pct": 80},
        {"FF_pph": 3400, "RPM_pct": 85},
        {"FF_pph": 4800, "RPM_pct": 90},
        {"FF_pph": 7000, "RPM_pct": 95},
        {"FF_pph": 10000, "RPM_pct": 99},
    ]).to_csv(tmp_path / "f110_ff_to_rpm_knots.csv", index=False)

    landing_rows = [{
        "flap_setting": "DOWN", "gross_weight_lbs": 54000,
        "pressure_alt_ft": 0, "temp_F": 59, "headwind_kt": 0,
        "ground_roll_ft_unfactored": 2800,
    }]
    pd.DataFrame(landing_rows).to_csv(tmp_path / "f14_landing_natops_full.csv", index=False)

    cruise_rows = [{
        "gross_weight_lbs": 65000, "drag_index": 0,
        "optimum_alt_ft": 33900, "optimum_mach": 0.718,
        "source_note": "test table",
    }]
    pd.DataFrame(cruise_rows).to_csv(tmp_path / "f14_cruise_natops.csv", index=False)

    airport_rows = [{
        "map": "Test", "airport_name": "Field", "runway_pair": "09/27",
        "runway_end": "09", "heading_deg": 90, "length_ft": 8000,
        "tora_ft": 8000, "toda_ft": 8200, "asda_ft": 8100,
        "threshold_elev_ft": 100, "opp_threshold_elev_ft": 120,
        "slope_percent": None, "notes": "fixture",
    }]
    pd.DataFrame(airport_rows).to_csv(tmp_path / "dcs_airports.csv", index=False)
    return tmp_path
