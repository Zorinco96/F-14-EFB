from __future__ import annotations

from dataclasses import asdict, replace
import re

import pandas as pd
import streamlit as st

from src.f14perf.airport import AirportDatabase
from src.f14perf.atmosphere import pressure_altitude_ft
from src.f14perf.climb import ClimbModel
from src.f14perf.cruise import CruiseModel
from src.f14perf.energy import EnergyModel
from src.f14perf.engine import F110Deck
from src.f14perf.fuel import FuelModel
from src.f14perf.kneeboard import render_kneeboard_png
from src.f14perf.landing import LandingModel
from src.f14perf.loadout import (
    LOADOUT_PRESETS,
    STATION_OPTIONS,
    STORE_CATALOG,
    Loadout,
    loadout_from_preset,
)
from src.f14perf.takeoff import AutoTakeoffSelector, TakeoffModel
from src.f14perf.types import Environment, Runway, TakeoffInputs
from src.f14perf.weather import parse_metar, wind_components


st.set_page_config(page_title="F-14 EFB", page_icon="✈", layout="wide")
st.markdown(
    """
    <style>
    .block-container {padding-top: 1.5rem; padding-bottom: 2rem;}
    [data-testid="stMetric"] {
        background: #0f2234;
        border: 1px solid #29445d;
        border-radius: 0.55rem;
        padding: 0.7rem 0.8rem;
    }
    [data-testid="stSidebar"] {border-right: 1px solid #20364a;}
    .stTabs [data-baseweb="tab-list"] {gap: 0.25rem;}
    .stTabs [data-baseweb="tab"] {min-height: 2.8rem;}
    div[data-testid="stStatusWidget"] {border-radius: 0.5rem;}
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("F-14 EFB")
st.caption("vTF-77 DCS mission planning and kneeboard generator")

MODEL_REVISION = "2026-08-16-tacview-reconciliation"


@st.cache_resource
def airport_db(model_revision: str):
    _ = model_revision
    return AirportDatabase()


@st.cache_resource
def models(model_revision: str):
    _ = model_revision
    return {
        "takeoff_auto": AutoTakeoffSelector(),
        "takeoff": TakeoffModel(),
        "climb": ClimbModel(),
        "cruise": CruiseModel(),
        "landing": LandingModel(),
        "energy": EnergyModel(),
        "fuel": FuelModel(),
    }


@st.cache_resource
def takeoff_engine():
    return F110Deck()


def source_block(provenance, notes: list[str] | None = None):
    with st.expander("Method and source"):
        st.write(f"**{provenance.label}**: {provenance.source}")
        if provenance.detail:
            st.caption(provenance.detail)
        if provenance.confidence:
            st.caption(provenance.confidence)
        for note in notes or []:
            st.write(f"- {note}")


def checkpoint_rows(points):
    return [
        point
        for index, point in enumerate(points)
        if point.altitude_ft == 1_000
        or point.altitude_ft == 10_000
        or point.altitude_ft % 5_000 == 0
        or index == len(points) - 1
    ]


st.sidebar.markdown("## Flight setup")
mission_name = st.sidebar.text_input("Mission / callsign", "vTF-77 Mission")

with st.sidebar.expander("Mission essentials", expanded=True):
    takeoff_weight = st.number_input("Takeoff gross weight (lb)", 40_000, 76_000, 65_000, 500)
    landing_weight = st.number_input("Planned landing gross weight (lb)", 40_000, 76_000, 54_000, 500)
    starting_fuel = st.number_input("Starting fuel (lb)", 0, 20_000, 16_000, 500)
    route_nm = st.number_input(
        "Cruise leg distance (NM)",
        0.0,
        3_000.0,
        300.0,
        25.0,
        help="Distance modeled at the displayed cruise condition. Climb is calculated separately.",
    )
    bingo = st.number_input("BINGO fuel (lb)", 0, 15_000, 4_000, 500)
    joker_margin = st.number_input("JOKER above BINGO (lb)", 0, 10_000, 2_000, 500)

with st.sidebar.expander("Aircraft and loadout", expanded=False):
    loadout_preset = st.selectbox(
        "Preset",
        [*LOADOUT_PRESETS, "Custom station loadout"],
    )
    if loadout_preset == "Custom station loadout":
        selected_stations: dict[str, str] = {}
        st.caption("Stations run from left glove/wing to right glove/wing.")
        for station, options in STATION_OPTIONS.items():
            selected_stations[station] = st.selectbox(
                f"STA {station}",
                options,
                format_func=lambda key: STORE_CATALOG[key].label,
                key=f"loadout_station_{station}",
            )
        loadout = Loadout(selected_stations)
    else:
        loadout = loadout_from_preset(loadout_preset)
    st.caption(loadout.summary)

drag_index = loadout.model_drag_index

runway_entry_note = ""
with st.sidebar.expander("Departure runway", expanded=True):
    runway_source = st.radio("Source", ["DCS airport database", "Manual"])
    runway_condition = st.selectbox("Condition", ["DRY", "WET"])
    if runway_source == "DCS airport database":
        db = airport_db(MODEL_REVISION)
        map_name = st.selectbox("DCS map", db.maps)
        airport = st.selectbox("Airfield", db.airports(map_name))
        runway_end = st.selectbox("Runway", db.runway_ends(map_name, airport))
        airport_selection = db.get(map_name, airport, runway_end, runway_condition)
        runway = airport_selection.runway
        landing_runway = runway
        entry_options = ["Full length"]
        if airport_selection.dcs_runway_start_tora_ft is not None:
            entry_options.insert(0, "DCS runway start")
        entry_options.append("Custom available distance")
        runway_entry = st.selectbox(
            "Runway entry",
            entry_options,
            help="DCS runway-start spawns can be well beyond the physical threshold. Use the distance actually available from brake release.",
        )
        if runway_entry == "DCS runway start":
            available = float(airport_selection.dcs_runway_start_tora_ft)
            runway = replace(runway, tora_ft=available, toda_ft=available, asda_ft=available)
            runway_entry_note = airport_selection.runway_start_note
        elif runway_entry == "Custom available distance":
            available = st.number_input(
                "Available from brake release (ft)",
                500.0,
                20_000.0,
                float(runway.tora_ft),
                100.0,
            )
            runway = replace(runway, tora_ft=available, toda_ft=available, asda_ft=available)
            runway_entry_note = "User-entered distance from brake release to runway end."
        st.caption(
            f"HDG {runway.heading_deg:.0f}° | TORA {runway.tora_ft:.0f} | "
            f"TODA {runway.toda_ft:.0f} | ASDA {runway.asda_ft:.0f} ft"
        )
        if runway_entry_note:
            st.caption(runway_entry_note)
    else:
        heading = st.number_input("Runway heading (deg)", 0.0, 360.0, 0.0, 1.0)
        tora = st.number_input("TORA (ft)", 500.0, 20_000.0, 8_000.0, 100.0)
        toda = st.number_input("TODA (ft)", 500.0, 25_000.0, float(tora), 100.0)
        asda = st.number_input("ASDA (ft)", 500.0, 25_000.0, float(tora), 100.0)
        elev = st.number_input("Threshold elevation (ft)", -1_500.0, 15_000.0, 0.0, 100.0)
        slope = st.number_input("Runway slope (%)", -5.0, 5.0, 0.0, 0.1)
        runway = Runway(
            name="Manual runway",
            heading_deg=heading,
            tora_ft=tora,
            toda_ft=toda,
            asda_ft=asda,
            slope_pct=slope,
            condition=runway_condition,
            elevation_ft=elev,
        )
        landing_runway = runway

weather_notes: list[str] = []
with st.sidebar.expander("Weather", expanded=True):
    weather_mode = st.radio("Input", ["Manual", "METAR paste"])
    default_elev = runway.elevation_ft if runway.elevation_ft is not None else 0.0
    parsed_environment = None
    if weather_mode == "METAR paste":
        raw_metar = st.text_area(
            "METAR",
            placeholder="KLSV 152355Z 22012G20KT 10SM FEW100 35/08 A2985",
        )
        if raw_metar.strip():
            parsed = parse_metar(raw_metar, default_elev)
            parsed_environment = parsed.environment
            weather_notes = parsed.notes
            st.caption(
                f"OAT {parsed_environment.oat_c:.0f} C | QNH {parsed_environment.qnh_inhg:.2f} | "
                f"wind {('VRB' if parsed_environment.wind_dir_deg is None else f'{parsed_environment.wind_dir_deg:.0f}°')} "
                f"{parsed_environment.wind_speed_kt:.0f} kt"
            )
    if parsed_environment is None:
        oat = st.number_input("OAT (°C)", -60.0, 60.0, 15.0, 1.0)
        qnh = st.number_input("QNH (inHg)", 27.00, 31.50, 29.92, 0.01)
        wind_dir = st.number_input("Wind direction (deg)", 0.0, 360.0, 0.0, 10.0)
        wind_speed = st.number_input("Wind speed (kt)", 0.0, 80.0, 0.0, 1.0)
        environment = Environment(
            field_elevation_ft=default_elev,
            oat_c=oat,
            qnh_inhg=qnh,
            wind_dir_deg=wind_dir if wind_speed > 0 else None,
            wind_speed_kt=wind_speed,
        )
    else:
        environment = parsed_environment

with st.sidebar.expander("Takeoff setup", expanded=True):
    flaps = st.selectbox("Takeoff flaps", ["UP", "MANEUVER", "FULL"])
    power_setting = st.radio(
        "Takeoff power",
        ["MIL", "Reduced dry test"],
        help="FF is the primary cockpit cue. RPM and nozzle position are cross-checks.",
    )
    if power_setting == "MIL":
        rpm = 100.0
        st.info("SET MIL: approximately 10,100 PPH per engine. Cross-check 95-104% N2 and 3-10% nozzle.")
    else:
        target_ff = st.slider(
            "Target FF per engine (PPH)",
            3_400,
            10_000,
            6_000,
            100,
            help="DCS test setting. The app converts the selected FF to an expected RPM using the limited observation set.",
        )
        field_elev_for_power = runway.elevation_ft
        if field_elev_for_power is None:
            field_elev_for_power = environment.field_elevation_ft
        takeoff_pa = pressure_altitude_ft(field_elev_for_power, environment.qnh_inhg)
        inverse_power = takeoff_engine().rpm_for_takeoff_ff(
            target_ff,
            takeoff_pa,
            environment.oat_c,
        )
        rpm = float(inverse_power.rpm_pct)
        st.caption(f"Expected EIG cross-check: approximately {rpm:.1f}% N2. Reduced-power runway performance is test-only.")

with st.sidebar.expander("Advanced planning policy", expanded=False):
    runway_factor = st.number_input("Runway factor", 1.00, 1.50, 1.15, 0.01)
    climb_gate = st.number_input("Initial AEO climb gate (ft/NM)", 0, 1_000, 300, 25)
    wind_policy = st.radio("Takeoff wind policy", ["0% HW / 150% TW", "50% HW / 150% TW"])
    climb_choice = st.radio("Mission climb", ["MIL climb", "95% dry economy"])
    isa_delta = st.number_input("ISA deviation climb/cruise (°C)", -30.0, 40.0, 0.0, 1.0)

headwind_credit = 0.0 if wind_policy.startswith("0%") else 50.0
climb_strategy = "MINIMUM_TIME" if climb_choice == "MIL climb" else "MOST_EFFICIENT"

inputs = TakeoffInputs(
    weight_lb=float(takeoff_weight),
    environment=environment,
    runway=runway,
    flaps=flaps,
    thrust="MANUAL",
    rpm_pct=float(rpm),
    runway_factor=float(runway_factor),
    climb_target_ft_nm=float(climb_gate),
    headwind_credit_pct=headwind_credit,
    tailwind_penalty_pct=150.0,
    takeoff_loadout=loadout.summary,
)

m = models(MODEL_REVISION)
dcs_engine_observations = pd.read_csv("data/dcs_engine_observations.csv")
dcs_takeoff_observations = pd.read_csv("data/dcs_takeoff_test_log.csv")
tacview_takeoff_motion = pd.read_csv("data/tacview_takeoff_motion.csv")

try:
    takeoff = m["takeoff_auto"].select(inputs)
    cruise = m["cruise"].optimum(takeoff_weight, drag_index, isa_delta)
    climb_profile = m["climb"].profile(
        takeoff_weight,
        isa_delta_c=isa_delta,
        drag_index=drag_index,
        target_gradient_ft_nm=climb_gate,
        end_alt_ft=int(cruise.optimum_altitude_ft),
        strategy=climb_strategy,
    )
    climb_schedule = climb_profile.points
    landing = m["landing"].calculate(
        landing_weight,
        environment,
        landing_runway,
        "DOWN",
        runway_factor,
    )
    landing_fuel = m["landing"].fuel_reference(
        takeoff_weight,
        starting_fuel,
        loadout.expendable_credit_weight_lb,
    )
except Exception as exc:
    st.error(f"Performance model error: {exc}")
    st.stop()

headwind, crosswind = wind_components(
    environment.wind_dir_deg,
    environment.wind_speed_kt,
    runway.heading_deg,
)
matching_tacview_runs = tacview_takeoff_motion[
    tacview_takeoff_motion["airport"].fillna("").map(
        lambda name: bool(name) and name in runway.name
    )
    & tacview_takeoff_motion["runway"].fillna("").map(
        lambda end: bool(end) and runway.name.endswith(f"RWY {end}")
    )
    & (tacview_takeoff_motion["flaps_label"] == takeoff.flaps)
]
correlated_tacview_runs = matching_tacview_runs[
    matching_tacview_runs["configuration_status"] == "CORRELATED_USER_SEQUENCE"
]

takeoff_status = (
    "PLANNING HOLD"
    if not takeoff.takeoff_data_valid
    else ("REFERENCE ONLY" if takeoff.feasible else "LIMIT EXCEEDED")
)
fuel = m["fuel"].plan(
    starting_fuel,
    route_nm,
    climb_schedule,
    cruise,
    bingo,
    joker_margin,
)

advisories = [
    *weather_notes,
    *takeoff.warnings,
    *landing.warnings,
    *fuel.warnings,
]
if landing_weight > landing_fuel.field_limit_lb:
    advisories.append(
        f"Planned landing gross weight exceeds the {landing_fuel.field_limit_lb:,.0f} lb field landing limit."
    )
advisories = list(dict.fromkeys(note for note in advisories if note))

summary1, summary2, summary3, summary4 = st.columns(4)
summary1.metric("Departure", takeoff_status, f"{takeoff.flaps} / {takeoff.thrust_setting}")
summary2.metric(
    "SET FF / engine",
    f"{takeoff.fuel_flow_pph_per_engine:,.0f} PPH",
    "PRIMARY TAKEOFF THRUST CUE",
)
summary3.metric(
    "Vr / V2 reference",
    f"{takeoff.vr_kt:.0f} / {takeoff.v2_kt:.0f} KIAS",
    f"trial trim {takeoff.stabilizer_trim_anu:.1f} ANU",
)
summary4.metric("Recovery", f"{landing_weight/1000:.1f}K lb", "15 units AOA")

mission_tab, takeoff_tab, enroute_tab, recovery_tab, maneuver_tab, kneeboard_tab, data_tab = st.tabs(
    ["Quick Plan", "Takeoff", "Enroute", "Recovery", "Tools", "Kneeboard", "Data"]
)

with mission_tab:
    if takeoff_status == "PLANNING HOLD":
        st.warning("Planning hold: the selected stores or hot/high reduced-thrust condition is outside the validated DCS takeoff set.")
    elif takeoff_status == "LIMIT EXCEEDED":
        st.error("The legacy takeoff result exceeds the configured runway or climb planning limit.")
    else:
        st.info("Reference only: configured planning margins are positive. Legacy V-speeds and distances are not NATOPS-verified and are not a GO call.")

    if advisories:
        with st.expander(f"Planning notes ({len(advisories)})"):
            for note in advisories:
                st.write(f"- {note}")

    st.subheader("Mission card")
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Runway", runway.name, f"{runway.tora_ft:,.0f} ft TORA")
    mc2.metric("Wind", f"{headwind:+.0f} kt HW", f"{abs(crosswind):.0f} kt XW")
    mc3.metric("Gross weight", f"{takeoff_weight:,.0f} lb")
    mc4.metric("Stores", loadout_preset if loadout_preset != "Custom station loadout" else "Custom")

    v1, v2, v3, v4 = st.columns(4)
    v1.metric("V1", "WITHHELD", "engine-cut data required")
    v2.metric("Vr reference", f"{takeoff.vr_kt:.0f} KIAS")
    v3.metric("V2 reference", f"{takeoff.v2_kt:.0f} KIAS")
    v4.metric("Vfs estimate", f"{takeoff.vfs_kt:.0f} KIAS")

    t1, t2, t3, t4 = st.columns(4)
    t1.metric("Pre-roll trim", f"{takeoff.stabilizer_trim_anu:.1f} ANU")
    t2.metric("OEI target", f"{takeoff.oei_climb_speed_kt:.0f} KIAS", "V2 + 15")
    t3.metric("Takeoff thrust set", f"{takeoff.fuel_flow_pph_per_engine:,.0f} PPH/eng", "FF PRIMARY • RPM CROSS-CHECK")
    t4.metric("OEI configuration", "GEAR UP / MIL", "OPERATING ENGINE")

    mission_plan_df = pd.DataFrame(
        [
            {
                "Phase": "Climb allowance",
                "Plan": f"{climb_profile.time_min:.0f} min / {climb_profile.fuel_burn_lb:,.0f} lb total",
                "Data status": "Guarded model",
            },
            {
                "Phase": "Cruise",
                "Plan": (
                    f"FL{cruise.flight_level:03d} | {cruise.optimum_ias_kt:.0f} KIAS / M{cruise.optimum_mach:.2f} | "
                    f"trial {cruise.fuel_flow_pph_per_engine:,.0f} PPH/eng / {cruise.rpm_pct:.0f}%"
                ),
                "Data status": "Unverified legacy trial target",
            },
            {
                "Phase": "Recovery",
                "Plan": (
                    f"15 units AOA | DLC neutral ~{landing.on_speed_ias_est_kt:.0f} +/-"
                    f"{landing.on_speed_ias_tolerance_kt:.0f} KIAS"
                ),
                "Data status": "NATOPS flight-test chart",
            },
            {
                "Phase": "Fuel",
                "Plan": (
                    f"Burn {fuel.mission_burn_lb:,.0f} | land {fuel.landing_fuel_lb:,.0f} | "
                    f"JOKER {fuel.joker_lb:,.0f} | BINGO {fuel.bingo_lb:,.0f} lb"
                ),
                "Data status": "Planning total rounded up",
            },
        ]
    )
    st.dataframe(mission_plan_df, width="stretch", hide_index=True)

with takeoff_tab:
    st.subheader("Takeoff setup")
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Flaps", takeoff.flaps)
    p2.metric("SET FF / engine", f"{takeoff.fuel_flow_pph_per_engine:,.0f} PPH", "PRIMARY")
    if takeoff.rpm_pct >= 99.5:
        p3.metric("RPM cross-check", "95-104% N2", "matched tapes")
        p4.metric("Nozzle cross-check", "3-10%", "MIL")
    else:
        p3.metric("RPM cross-check", f"~{takeoff.eig_reference_rpm_pct:.1f}% N2", "observation-derived")
        p4.metric("Power status", "TEST ONLY", "reduced dry")
    st.caption("FF is the primary takeoff thrust-set indication. RPM and nozzle position are secondary cross-checks; verify matched left/right indications.")

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("V1", "WITHHELD", "no engine-cut validation")
    s2.metric("Vr reference", f"{takeoff.vr_kt:.0f} kt")
    s3.metric("V2 reference", f"{takeoff.v2_kt:.0f} kt")
    s4.metric("Vfs estimate", f"{takeoff.vfs_kt:.0f} kt")

    tr1, tr2, tr3 = st.columns(3)
    trim_band = takeoff.stabilizer_trim_band_anu
    trim_detail = (
        f"prior {trim_band[0]:.1f}; next trial {trim_band[1]:.1f}"
        if trim_band
        else "unvalidated baseline"
    )
    tr1.metric("Pre-roll trial trim", f"{takeoff.stabilizer_trim_anu:.1f} ANU", trim_detail)
    tr2.metric("OEI climb", f"{takeoff.oei_climb_speed_kt:.0f} KIAS", "gear up")
    tr3.metric("OEI power", "MIL", "operating engine")
    st.caption(takeoff.stabilizer_trim_note)

    d1, d2, d3, d4 = st.columns(4)
    distance_note = "legacy estimate; not NATOPS-verified"
    d1.metric("Legacy ASD estimate", f"{takeoff.asd_ft:,.0f} ft", f"{takeoff.factored_asd_ft:,.0f} ft factored")
    d2.metric("Legacy AEO distance", f"{takeoff.agd_ft:,.0f} ft", f"{takeoff.factored_agd_ft:,.0f} ft factored")
    d3.metric("Planning ASDA margin", f"{takeoff.asda_margin_ft:+,.0f} ft")
    d4.metric("Planning TODA margin", f"{takeoff.toda_margin_ft:+,.0f} ft")
    st.caption(distance_note)

    observed_liftoff_runs = correlated_tacview_runs.dropna(subset=["liftoff_distance_ft"])
    if not observed_liftoff_runs.empty and 94.5 <= takeoff.rpm_pct <= 95.5:
        observed = observed_liftoff_runs.iloc[-1]
        st.markdown("**Correlated attached Tacview sequence**")
        o1, o2, o3, o4 = st.columns(4)
        o1.metric("Stick rotation report", "143 KIAS", "user observation")
        o2.metric("Tacview pitch response", f"{observed['pitch_response_ias_kt']:.0f} KIAS")
        o3.metric("Tacview AEO liftoff", f"{observed['liftoff_distance_ft']:,.0f} ft", "from brake release")
        o4.metric("Measured available", "~4,800 ft", "+/-100 ft")
        model_gap = observed["liftoff_distance_ft"] - takeoff.agd_ft
        st.caption(
            f"Tacview pitch response followed the reported stick-rotation cue by about {observed['pitch_response_ias_kt'] - 143:+.0f} kt. "
            f"Measured liftoff was {model_gap:+,.0f} ft relative to the unfactored legacy AEO-distance estimate. "
            "Tacview contains throttle ratio but no per-engine FF or RPM telemetry, so it is not used to fit engine data."
        )
    if not matching_tacview_runs.empty:
        with st.expander(f"Attached Tacview motion, same flap setting ({len(matching_tacview_runs)})"):
            st.dataframe(
                matching_tacview_runs[
                    [
                        "recording_time",
                        "median_throttle_ratio",
                        "pitch_response_ias_kt",
                        "liftoff_ias_kt",
                        "liftoff_distance_ft",
                        "configuration_status",
                    ]
                ],
                width="stretch",
                hide_index=True,
            )
            st.caption("Runs without recorded gross weight, trim, OAT, and cockpit indications remain motion evidence only.")
    source_block(takeoff.provenance, takeoff.notes)

with enroute_tab:
    st.subheader(f"Climb planning allowance to FL{cruise.flight_level:03d}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Time allowance", f"{climb_profile.time_min:.0f} min", "rounded up")
    c2.metric("Fuel allowance", f"{climb_profile.fuel_burn_lb:,.0f} lb", "two-engine total; rounded up")
    c3.metric("MIL climb technique", "6.0 → 9.5 AOA", "sea level → combat ceiling")
    c4.metric("Data status", "ALLOWANCE", "not predicted performance")
    st.caption(
        "NATOPS Figure 14-1 supports the AOA technique. The app does not have a verified F-14B climb chart, so time, fuel, speed, FF, RPM, ROC, and gradient remain conservative engineering allowances."
    )
    with st.expander("Estimated climb checkpoints"):
        climb_df = pd.DataFrame(
            [
                {
                    "Altitude": f"{point.altitude_ft:,.0f} ft",
                    "KIAS": f"{point.ias_kt:.0f}",
                    "TAS": f"{point.tas_kt:.0f}",
                    "RPM": f"{point.rpm_pct:.0f}%",
                    "Planning ROC": f"{point.roc_fpm:,.0f} fpm",
                    "Gradient": f"{point.gradient_ft_nm:,.0f} ft/NM",
                    "FF / engine": f"{point.fuel_flow_pph_per_engine:,.0f} PPH",
                }
                for point in checkpoint_rows(climb_schedule)
            ]
        )
        st.dataframe(climb_df, width="stretch", hide_index=True)

    st.subheader("Legacy cruise trial")
    cr1, cr2, cr3, cr4 = st.columns(4)
    cr1.metric("Trial flight level", f"FL{cruise.flight_level:03d}", "legacy unverified table")
    cr2.metric("Technique", "8.0 units AOA", "NATOPS optimum-altitude cruise")
    cr3.metric("Trial FF / engine", f"{cruise.fuel_flow_pph_per_engine:,.0f} PPH", "planning allowance")
    cr4.metric("RPM cross-check", f"~{cruise.rpm_pct:.0f}%", "uncalibrated model")
    st.caption(
        f"Trial speed {cruise.optimum_ias_kt:.0f} KIAS / M{cruise.optimum_mach:.3f}, TAS {cruise.tas_kt:.0f} kt. The prior cruise-table citation pointed to a pocket checklist that cannot contain the claimed page; altitude, Mach, FF, and RPM remain unverified until a controlled DCS calibration is captured."
    )
    source_block(climb_profile.provenance, climb_profile.notes)
    source_block(cruise.provenance, cruise.notes)

with recovery_tab:
    st.subheader("Landing fuel quick reference")
    st.caption(
        "Maximum fuel is calculated from entered takeoff gross weight and starting fuel. "
        "Values are rounded down to the nearest 100 lb. The 54,000 lb carrier/FCLP limit assumes the B(U)-appropriate AYC-679 or AYC-805 modification; the unmodified limit is 51,800 lb."
    )
    limits_df = pd.DataFrame(
        [
            {
                "Store condition": "All stores retained",
                "Field, 60,000 lb": f"{landing_fuel.field_retained_fuel_lb:,.0f} lb",
                "Carrier, 54,000 lb": f"{landing_fuel.carrier_retained_fuel_lb:,.0f} lb",
            },
            {
                "Store condition": "All expendable stores expended",
                "Field, 60,000 lb": f"{landing_fuel.field_expended_fuel_lb:,.0f} lb",
                "Carrier, 54,000 lb": f"{landing_fuel.carrier_expended_fuel_lb:,.0f} lb",
            },
        ]
    )
    st.dataframe(limits_df, width="stretch", hide_index=True)
    st.caption(
        f"Retained zero-fuel weight: {landing_fuel.retained_zero_fuel_weight_lb:,.0f} lb | "
        f"Conservative expendable credit: {landing_fuel.expendable_credit_lb:,.0f} lb"
    )

    st.subheader("Field landing")
    l1, l2, l3, l4 = st.columns(4)
    l1.metric("Planned gross weight", f"{landing_weight:,.0f} lb")
    l2.metric("Legacy ground-roll estimate", f"{landing.ground_roll_ft:,.0f} ft")
    l3.metric("Factored planning distance", f"{landing.factored_distance_ft:,.0f} ft")
    l4.metric("Planning runway margin", f"{landing.runway_margin_ft:+,.0f} ft")
    l5, l6, l7 = st.columns(3)
    l5.metric("On-speed reference", "15 units AOA")
    l6.metric(
        "Normal DLC neutral",
        f"~{landing.on_speed_ias_est_kt:.0f} KIAS",
        f"+/-{landing.on_speed_ias_tolerance_kt:.0f} kt chart tolerance",
    )
    l7.metric("DLC stowed", f"~{landing.on_speed_ias_dlc_stowed_kt:.0f} KIAS")
    st.caption("NAVAIR 01-F14AAP-1 Figure 11-8 flight-test chart, 20-degree wing sweep, all drag indexes.")
    source_block(landing_fuel.provenance, landing_fuel.notes)
    source_block(landing.provenance)

with maneuver_tab:
    st.subheader("Level-turn geometry")
    st.caption(
        "This section now calculates ideal coordinated-turn geometry only. "
        "The previous Ps and sustained-turn estimates were removed because the underlying F-14B polar was not validated."
    )
    e1, e2, e3 = st.columns(3)
    energy_alt = e1.number_input("Altitude (ft)", 0, 50_000, 10_000, 1_000)
    energy_ias = e2.number_input("Speed (KIAS)", 120, 800, 350, 10)
    planning_g = e3.number_input(
        "Planning G",
        1.5,
        7.5,
        4.0,
        0.5,
        help="User planning input. The EFB does not assert that the selected value is available or structurally permitted.",
    )
    energy = m["energy"].calculate(
        takeoff_weight,
        energy_alt,
        energy_ias,
        drag_index,
        planning_g,
        "MIL",
        isa_delta,
    )
    q1, q2, q3, q4 = st.columns(4)
    q1.metric("TAS / Mach", f"{energy.speed_tas_kt:.0f} kt", f"M {energy.mach:.3f}")
    q2.metric("Turn rate", f"{energy.turn_rate_dps:.1f}°/s", f"{energy.planning_g:.1f} G")
    q3.metric("Turn radius", f"{energy.turn_radius_ft:,.0f} ft")
    q4.metric("180° / 360°", f"{energy.turn_180_sec:.1f} / {energy.turn_360_sec:.1f} sec")
    source_block(energy.provenance)

kneeboard_rpm_crosscheck = (
    "95-104%" if takeoff.rpm_pct >= 99.5 else f"~{takeoff.eig_reference_rpm_pct:.1f}%"
)
kneeboard_sections = [
    (
        "Takeoff",
        [
            f"{runway.name} | {takeoff_weight:,.0f} LB | {headwind:+.0f} KT HW | {abs(crosswind):.0f} KT XW",
            f"{takeoff.flaps} / {takeoff.thrust_setting} | TRIM TRIAL {takeoff.stabilizer_trim_anu:.1f} ANU | {takeoff_status}",
        ],
    ),
    (
        "Speeds",
        [
            f"V1 WITHHELD | VR REF {takeoff.vr_kt:.0f} | V2 REF {takeoff.v2_kt:.0f} | VFS EST {takeoff.vfs_kt:.0f} KIAS",
            f"OEI {takeoff.oei_climb_speed_kt:.0f} KIAS (V2+15) | GEAR UP | OPERATING ENGINE MIL",
        ],
    ),
    (
        "Power and runway",
        [
            f"SET {takeoff.fuel_flow_pph_per_engine:,.0f} PPH/ENG PRIMARY | RPM X-CHECK {kneeboard_rpm_crosscheck}",
            f"LEGACY ASD {takeoff.factored_asd_ft:,.0f} | AEO {takeoff.factored_agd_ft:,.0f} | PLAN MARGIN {min(takeoff.asda_margin_ft, takeoff.toda_margin_ft):+,.0f} FT",
        ],
    ),
    (
        "Climb and cruise",
        [
            f"MIL CLIMB 6.0->9.5 AOA | PLAN ALLOW {climb_profile.time_min:.0f} MIN / {climb_profile.fuel_burn_lb:,.0f} LB",
            f"CRUISE TRIAL: FL{cruise.flight_level:03d} | 8.0 AOA | {cruise.fuel_flow_pph_per_engine:,.0f} PPH/ENG / ~{cruise.rpm_pct:.0f}%",
        ],
    ),
    (
        "Recovery",
        [
            f"PLAN {landing_weight:,.0f} LB | 15 AOA | DLC NEUTRAL ~{landing.on_speed_ias_est_kt:.0f} +/-{landing.on_speed_ias_tolerance_kt:.0f} KIAS",
            f"DLC STOWED ~{landing.on_speed_ias_dlc_stowed_kt:.0f} KIAS",
            f"MAX FUEL RET: FIELD {landing_fuel.field_retained_fuel_lb:,.0f} / CV {landing_fuel.carrier_retained_fuel_lb:,.0f} LB",
            f"MAX FUEL EXP: FIELD {landing_fuel.field_expended_fuel_lb:,.0f} / CV {landing_fuel.carrier_expended_fuel_lb:,.0f} LB",
        ],
    ),
    (
        "Fuel",
        [
            f"START {starting_fuel:,.0f} | PLAN BURN {fuel.mission_burn_lb:,.0f} | LAND {fuel.landing_fuel_lb:,.0f} LB",
            f"JOKER {fuel.joker_lb:,.0f} | BINGO {fuel.bingo_lb:,.0f} LB",
        ],
    ),
]
if not observed_liftoff_runs.empty and 94.5 <= takeoff.rpm_pct <= 95.5:
    observed = observed_liftoff_runs.iloc[-1]
    kneeboard_sections.insert(
        3,
        (
            "Matching DCS test",
            [
                f"TACVIEW PITCH RESPONSE {observed['pitch_response_ias_kt']:.0f} KIAS | AEO LIFTOFF {observed['liftoff_distance_ft']:,.0f} FT",
                "USER: ROTATION INPUT 143 KIAS / TRIM 6.5 ANU HEAVY | AVAILABLE ~4,800 FT",
            ],
        ),
    )
kneeboard_png = render_kneeboard_png(
    mission_name or "vTF-77 Mission",
    f"F-14B(U) | {loadout_preset} | {MODEL_REVISION}",
    kneeboard_sections,
    footer=f"DCS ONLY | {takeoff_status}",
)

with kneeboard_tab:
    st.subheader("DCS kneeboard")
    kb1, kb2 = st.columns([1, 1])
    with kb1:
        st.image(kneeboard_png, caption="768 x 1024 mission card")
    with kb2:
        safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", mission_name).strip("_") or "F14_EFB"
        st.download_button(
            "Download kneeboard PNG",
            data=kneeboard_png,
            file_name=f"{safe_name}_kneeboard.png",
            mime="image/png",
            type="primary",
        )
        st.write("Place the PNG in your DCS kneeboard folder or add it to the mission package.")
        st.caption("The download updates automatically when mission inputs change.")

with data_tab:
    st.subheader("Audit status")
    audit_df = pd.DataFrame(
        [
            {"Area": "Takeoff", "Operational use": "Legacy grids + DCS observations", "Current treatment": "REFERENCE ONLY or HOLD; V1 withheld; no GO label"},
            {"Area": "Trim", "Operational use": "Controlled DCS trial schedule", "Current treatment": "5.5 UP / 7.0 MAN next candidates"},
            {"Area": "Climb", "Operational use": "NATOPS AOA technique + guarded allowance", "Current treatment": "6.0 to 9.5 units AOA; modeled details collapsed"},
            {"Area": "Cruise", "Operational use": "Unverified legacy trial", "Current treatment": "8 units AOA primary; altitude/Mach/FF/RPM require DCS calibration"},
            {"Area": "Landing", "Operational use": "Legacy ground roll + NATOPS Figure 11-8", "Current treatment": "DLC-neutral and DLC-stowed IAS shown with +/-4 kt"},
            {"Area": "Maneuver", "Operational use": "Kinematic geometry only", "Current treatment": "No Ps or sustained-capability claim"},
        ]
    )
    st.dataframe(audit_df, width="stretch", hide_index=True)
    st.caption(
        "Uncertainty is handled with conservative rounding, neutral data-status labels, planning holds, and one consolidated mission-notes panel."
    )
    st.subheader("Cross-checked anchors")
    anchors_df = pd.DataFrame(
        [
            {"Reference": "Henderson DCS runway start", "Known value": "~4,800 ft available (+/-100)", "Use": "Tacview geospatial reconciliation"},
            {"Reference": "Henderson MAN sequence", "Known value": "143 KIAS stick cue; 161 KIAS pitch response; 4,853 ft liftoff", "Use": "User report + attached Tacview"},
            {"Reference": "MIL engine indications", "Known value": "~10,100 PPH/eng; 95-104% N2; 3-10% nozzle", "Use": "NATOPS 2.11"},
            {"Reference": "54,000 lb on-speed", "Known value": "DLC neutral ~140 KIAS; DLC stowed ~131 KIAS; +/-4 kt", "Use": "NATOPS Figure 11-8"},
            {"Reference": "Landing gross weight", "Known value": "Field 60,000; modified carrier/FCLP 54,000; unmodified 51,800 lb", "Use": "NATOPS limit"},
            {"Reference": "Normal takeoff technique", "Known value": "MIL selected on roll; smooth rotation at precomputed Vr", "Use": "NATOPS procedure"},
        ]
    )
    st.dataframe(anchors_df, width="stretch", hide_index=True)
    st.markdown(
        "Sources: [Heatblur F-14 manual](https://f14.manuals.heatblur.se/) | "
        "[Heatblur flight-model audit](https://heatblur.se/fmupdate/) | "
        "[NAVAIR 01-F14AAP-1 public copy](https://server.3rd-wing.net/public/Bureau_VF31/Docs%20F-14%20r%C3%A9el/NAVAIR%2001-F14AAP-1%20-%20NATOPS%20Flight%20Manual%20-%20F-14B.pdf)"
    )
    with st.expander("DCS engine observations"):
        st.dataframe(dcs_engine_observations, width="stretch", hide_index=True)
    with st.expander("DCS takeoff observations"):
        st.dataframe(dcs_takeoff_observations, width="stretch", hide_index=True)
    with st.expander("Attached Tacview takeoff motion"):
        st.dataframe(tacview_takeoff_motion, width="stretch", hide_index=True)
    with st.expander("Raw takeoff result"):
        raw = asdict(takeoff)
        raw.pop("fuel_flow_pph_total", None)
        raw["provenance"] = asdict(takeoff.provenance)
        st.json(raw)

st.divider()
st.caption(
    "DCS simulation planning only. Not an approved real-world flight-performance source."
)
