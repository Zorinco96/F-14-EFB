from __future__ import annotations

from dataclasses import asdict
import re

import pandas as pd
import streamlit as st

from src.f14perf.airport import AirportDatabase
from src.f14perf.climb import ClimbModel
from src.f14perf.cruise import CruiseModel
from src.f14perf.energy import EnergyModel
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
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("F-14 EFB")
st.caption("vTF-77 DCS mission planning and kneeboard generator")

MODEL_REVISION = "2026-08-16-conservative-planning-audit"


@st.cache_resource
def airport_db():
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


st.sidebar.markdown("## Mission Setup")
mission_name = st.sidebar.text_input("Mission / callsign", "vTF-77 Mission")

with st.sidebar.expander("Aircraft and fuel", expanded=True):
    takeoff_weight = st.number_input("Takeoff gross weight (lb)", 40_000, 76_000, 65_000, 500)
    landing_weight = st.number_input("Planned landing gross weight (lb)", 40_000, 76_000, 54_000, 500)
    starting_fuel = st.number_input("Starting fuel (lb)", 0, 20_000, 16_000, 500)
    route_nm = st.number_input("Planned route distance (NM)", 0.0, 3_000.0, 300.0, 25.0)

with st.sidebar.expander("DCS loadout", expanded=True):
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

with st.sidebar.expander("Runway", expanded=True):
    runway_source = st.radio("Source", ["DCS airport database", "Manual"])
    runway_condition = st.selectbox("Condition", ["DRY", "WET"])
    if runway_source == "DCS airport database":
        db = airport_db()
        map_name = st.selectbox("DCS map", db.maps)
        airport = st.selectbox("Airfield", db.airports(map_name))
        runway_end = st.selectbox("Runway", db.runway_ends(map_name, airport))
        runway = db.get(map_name, airport, runway_end, runway_condition).runway
        st.caption(
            f"HDG {runway.heading_deg:.0f}° | TORA {runway.tora_ft:.0f} | "
            f"TODA {runway.toda_ft:.0f} | ASDA {runway.asda_ft:.0f} ft"
        )
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

with st.sidebar.expander("Planning policy"):
    flaps = st.selectbox("Takeoff flaps", ["AUTO", "UP", "MANEUVER", "FULL"])
    thrust_mode = st.selectbox(
        "Takeoff thrust",
        ["AUTO", "MANUAL"],
        index=1,
        help="MIL (100% command) is the conservative default. AUTO reduced thrust remains available for DCS test planning.",
    )
    rpm = st.slider("Takeoff RPM (%)", 85, 100, 100) if thrust_mode == "MANUAL" else None
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
    thrust=thrust_mode,
    rpm_pct=float(rpm) if rpm is not None else None,
    runway_factor=float(runway_factor),
    climb_target_ft_nm=float(climb_gate),
    headwind_credit_pct=headwind_credit,
    tailwind_penalty_pct=150.0,
    takeoff_loadout=loadout.summary,
)

m = models(MODEL_REVISION)
dcs_engine_observations = pd.read_csv("data/dcs_engine_observations.csv")
dcs_takeoff_observations = pd.read_csv("data/dcs_takeoff_test_log.csv")

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
    landing = m["landing"].calculate(landing_weight, environment, runway, "DOWN", runway_factor)
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
tank_count = sum(store == "FPU1" for store in loadout.normalized_stations.values())
aim9_count = sum(
    store in {"AIM9", "AIM9L", "AIM9M"}
    for store in loadout.normalized_stations.values()
)
matching_dcs_runs = dcs_takeoff_observations[
    dcs_takeoff_observations["airport"].fillna("").map(
        lambda name: bool(name) and name in runway.name
    )
    & dcs_takeoff_observations["runway"].fillna("").map(
        lambda end: bool(end) and runway.name.endswith(f"RWY {end}")
    )
    & (dcs_takeoff_observations["weight_lb"].sub(takeoff_weight).abs() <= 250)
    & (dcs_takeoff_observations["oat_c"].sub(environment.oat_c).abs() <= 1)
    & (dcs_takeoff_observations["flaps"] == takeoff.flaps)
    & (dcs_takeoff_observations["rpm_pct"].sub(takeoff.rpm_pct).abs() <= 0.5)
    & (dcs_takeoff_observations["external_tanks"] == tank_count)
    & (dcs_takeoff_observations["aim9_count"] == aim9_count)
]

takeoff_status = (
    "PLANNING HOLD"
    if not takeoff.takeoff_data_valid
    else ("MEETS PLAN" if takeoff.feasible else "DOES NOT MEET")
)

bingo = st.sidebar.number_input("BINGO fuel (lb)", 0, 15_000, 4_000, 500)
joker_margin = st.sidebar.number_input("JOKER above BINGO (lb)", 0, 10_000, 2_000, 500)
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

summary1, summary2, summary3, summary4, summary5 = st.columns(5)
summary1.metric("Takeoff plan", takeoff_status)
summary2.metric("Config", f"{takeoff.flaps} / {takeoff.thrust_setting}")
summary3.metric("V2 / trim", f"{takeoff.v2_kt:.0f} kt / {takeoff.stabilizer_trim_anu:.1f} ANU")
summary4.metric("Cruise", f"FL{cruise.flight_level:03d} / M{cruise.optimum_mach:.2f}")
summary5.metric("Recovery", f"{landing_weight/1000:.1f}K lb", "15 units AOA")

mission_tab, takeoff_tab, enroute_tab, recovery_tab, maneuver_tab, kneeboard_tab, data_tab = st.tabs(
    ["Mission", "Takeoff", "Climb & Cruise", "Recovery", "Maneuver", "Kneeboard", "Data"]
)

with mission_tab:
    if takeoff_status == "PLANNING HOLD":
        st.warning("Takeoff remains on planning hold for this loadout or condition. Values are retained for DCS test planning, not a GO call.")
    elif takeoff_status == "DOES NOT MEET":
        st.error("The current takeoff selection does not meet the runway or climb planning criteria.")
    else:
        st.success("The current takeoff selection meets the configured planning criteria.")

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
    v1.metric("V1", f"{takeoff.v1_kt:.0f} KIAS")
    v2.metric("Vr", f"{takeoff.vr_kt:.0f} KIAS")
    v3.metric("V2", f"{takeoff.v2_kt:.0f} KIAS")
    v4.metric("Vfs", f"{takeoff.vfs_kt:.0f} KIAS")

    t1, t2, t3, t4 = st.columns(4)
    t1.metric("Pre-roll trim", f"{takeoff.stabilizer_trim_anu:.1f} ANU")
    t2.metric("OEI target", f"{takeoff.oei_climb_speed_kt:.0f} KIAS", "V2 + 15")
    t3.metric("Power reference", f"{takeoff.rpm_pct:.0f}% command", f"{takeoff.fuel_flow_pph_per_engine:,.0f} PPH/eng")
    t4.metric("OEI configuration", "GEAR UP / MIL", "OPERATING ENGINE")

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Climb to cruise", f"{climb_profile.time_min:.1f} min", f"{climb_profile.fuel_burn_lb:,.0f} lb total")
    r2.metric("Cruise target", f"FL{cruise.flight_level:03d}", f"{cruise.optimum_ias_kt:.0f} KIAS / M{cruise.optimum_mach:.2f}")
    r3.metric("Cruise engine", f"{cruise.rpm_pct:.0f}% RPM", f"{cruise.fuel_flow_pph_per_engine:,.0f} PPH/eng")
    r4.metric("On-speed", "15 units AOA", f"~{landing.on_speed_ias_est_kt:.0f} KIAS")

    f1, f2, f3, f4 = st.columns(4)
    f1.metric("Mission burn", f"{fuel.mission_burn_lb:,.0f} lb")
    f2.metric("Landing fuel", f"{fuel.landing_fuel_lb:,.0f} lb")
    f3.metric("JOKER", f"{fuel.joker_lb:,.0f} lb")
    f4.metric("BINGO", f"{fuel.bingo_lb:,.0f} lb")

with takeoff_tab:
    st.subheader("Takeoff setup")
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Flaps", takeoff.flaps)
    p2.metric("Thrust", takeoff.thrust_setting)
    p3.metric("Commanded RPM", f"{takeoff.rpm_pct:.0f}% N2")
    p4.metric(
        "Observed EIG reference",
        f"{takeoff.eig_reference_rpm_pct:.0f}% N2",
        f"{takeoff.fuel_flow_pph_per_engine:,.0f} PPH per engine",
    )

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("V1", f"{takeoff.v1_kt:.0f} kt", f"table {takeoff.v1_reference_kt:.0f}")
    s2.metric("Vr", f"{takeoff.vr_kt:.0f} kt")
    s3.metric("V2", f"{takeoff.v2_kt:.0f} kt")
    s4.metric("Vfs", f"{takeoff.vfs_kt:.0f} kt")

    tr1, tr2, tr3 = st.columns(3)
    trim_band = takeoff.stabilizer_trim_band_anu
    trim_detail = f"trial {trim_band[0]:.1f}-{trim_band[1]:.1f}" if trim_band else "set before roll"
    tr1.metric("Pitch trim", f"{takeoff.stabilizer_trim_anu:.1f} ANU", trim_detail)
    tr2.metric("OEI climb", f"{takeoff.oei_climb_speed_kt:.0f} KIAS", "gear up")
    tr3.metric("OEI power", "MIL", "operating engine")
    st.caption(takeoff.stabilizer_trim_note)

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("ASD", f"{takeoff.asd_ft:,.0f} ft", f"factored {takeoff.factored_asd_ft:,.0f}")
    d2.metric("AGD", f"{takeoff.agd_ft:,.0f} ft", f"factored {takeoff.factored_agd_ft:,.0f}")
    d3.metric("ASDA margin", f"{takeoff.asda_margin_ft:+,.0f} ft")
    d4.metric("TODA margin", f"{takeoff.toda_margin_ft:+,.0f} ft")

    observed_liftoff_runs = matching_dcs_runs.dropna(subset=["liftoff_distance_ft"])
    if not observed_liftoff_runs.empty:
        observed = observed_liftoff_runs.iloc[-1]
        st.markdown("**Matching DCS observation**")
        o1, o2, o3 = st.columns(3)
        o1.metric("Rotation", f"{observed['rotation_ias_kt']:.0f} KIAS")
        o2.metric("Liftoff distance", f"{observed['liftoff_distance_ft']:,.0f} ft")
        o3.metric("Runway remaining", f"{observed['liftoff_remaining_ft']:,.0f} ft")
        st.caption("AEO distance to liftoff only. It is not accelerate-go or 50 ft distance.")
    source_block(takeoff.provenance, takeoff.notes)

with enroute_tab:
    st.subheader(f"{climb_profile.label} to FL{cruise.flight_level:03d}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Planned time", f"{climb_profile.time_min:.1f} min")
    c2.metric("Planned fuel", f"{climb_profile.fuel_burn_lb:,.0f} lb", "aircraft total")
    c3.metric("Below 10K", "250 KIAS")
    c4.metric("Above 10K", "300 KIAS / M0.72")
    st.caption(
        "Climb rate is a conservative mission-planning allowance, not predicted maximum capability. "
        "Fuel-flow columns are PPH per engine."
    )
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

    st.subheader("Optimum cruise")
    cr1, cr2, cr3, cr4 = st.columns(4)
    cr1.metric("Usable flight level", f"FL{cruise.flight_level:03d}")
    cr2.metric("Cruise speed", f"{cruise.optimum_ias_kt:.0f} KIAS", f"M {cruise.optimum_mach:.3f}")
    cr3.metric("RPM", f"{cruise.rpm_pct:.0f}%")
    cr4.metric("Fuel flow", f"{cruise.fuel_flow_pph_per_engine:,.0f} PPH", "per engine")
    cr5, cr6, cr7 = st.columns(3)
    cr5.metric("TAS", f"{cruise.tas_kt:.0f} kt")
    cr6.metric("Specific range", f"{cruise.specific_range_nm_per_1000lb:.1f} NM/1,000 lb")
    cr7.metric("Endurance", f"{cruise.endurance_hr_per_1000lb:.3f} hr/1,000 lb")
    source_block(climb_profile.provenance, climb_profile.notes)
    source_block(cruise.provenance, cruise.notes)

with recovery_tab:
    st.subheader("Landing fuel quick reference")
    st.caption(
        "Maximum fuel is calculated from entered takeoff gross weight and starting fuel. "
        "Values are rounded down to the nearest 100 lb."
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
    l2.metric("Ground roll", f"{landing.ground_roll_ft:,.0f} ft")
    l3.metric("Factored distance", f"{landing.factored_distance_ft:,.0f} ft")
    l4.metric("Runway margin", f"{landing.runway_margin_ft:+,.0f} ft")
    l5, l6 = st.columns(2)
    l5.metric("On-speed reference", "15 units AOA")
    l6.metric("Estimated IAS", f"~{landing.on_speed_ias_est_kt:.0f} KIAS")
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

kneeboard_sections = [
    (
        "Takeoff",
        [
            f"{runway.name} | {takeoff_weight:,.0f} LB | {headwind:+.0f} KT HW | {abs(crosswind):.0f} KT XW",
            f"{takeoff.flaps} / {takeoff.thrust_setting} | TRIM {takeoff.stabilizer_trim_anu:.1f} ANU | STATUS {takeoff_status}",
        ],
    ),
    (
        "Speeds",
        [
            f"V1 {takeoff.v1_kt:.0f} | VR {takeoff.vr_kt:.0f} | V2 {takeoff.v2_kt:.0f} | VFS {takeoff.vfs_kt:.0f} KIAS",
            f"OEI {takeoff.oei_climb_speed_kt:.0f} KIAS (V2+15) | GEAR UP | OPERATING ENGINE MIL",
        ],
    ),
    (
        "Power and runway",
        [
            f"CMD {takeoff.rpm_pct:.0f}% | EIG REF {takeoff.eig_reference_rpm_pct:.0f}% | {takeoff.fuel_flow_pph_per_engine:,.0f} PPH/ENG",
            f"ASD {takeoff.factored_asd_ft:,.0f} | AGD {takeoff.factored_agd_ft:,.0f} | MARGIN {min(takeoff.asda_margin_ft, takeoff.toda_margin_ft):+,.0f} FT",
        ],
    ),
    (
        "Climb and cruise",
        [
            f"{climb_choice.upper()}: 250 KIAS TO 10K, 300 KIAS / M0.72 ABOVE | {climb_profile.time_min:.1f} MIN / {climb_profile.fuel_burn_lb:,.0f} LB",
            f"FL{cruise.flight_level:03d} | {cruise.optimum_ias_kt:.0f} KIAS / M{cruise.optimum_mach:.2f} | {cruise.rpm_pct:.0f}% | {cruise.fuel_flow_pph_per_engine:,.0f} PPH/ENG",
        ],
    ),
    (
        "Recovery",
        [
            f"PLAN {landing_weight:,.0f} LB | 15 UNITS AOA | ~{landing.on_speed_ias_est_kt:.0f} KIAS",
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
            {"Area": "Takeoff", "Operational use": "Legacy table + DCS calibration", "Current treatment": "Planning hold outside validated conditions"},
            {"Area": "Climb", "Operational use": "Guarded schedule", "Current treatment": "Optimizer removed; conservative time/fuel allowance"},
            {"Area": "Cruise", "Operational use": "Legacy optimum table", "Current treatment": "Rounded FL; KIAS, RPM, and PPH/engine estimated"},
            {"Area": "Landing", "Operational use": "Legacy ground-roll table", "Current treatment": "60K field / 54K carrier fuel quick reference"},
            {"Area": "Maneuver", "Operational use": "Kinematic geometry only", "Current treatment": "Ps and sustained-turn claims removed"},
        ]
    )
    st.dataframe(audit_df, width="stretch", hide_index=True)
    st.caption(
        "The application exposes fewer repeated warnings. Uncertainty is handled by conservative schedules, planning holds, "
        "and one consolidated mission-notes panel."
    )
    with st.expander("DCS engine observations"):
        st.dataframe(dcs_engine_observations, width="stretch", hide_index=True)
    with st.expander("DCS takeoff observations"):
        st.dataframe(dcs_takeoff_observations, width="stretch", hide_index=True)
    with st.expander("Raw takeoff result"):
        raw = asdict(takeoff)
        raw.pop("fuel_flow_pph_total", None)
        raw["provenance"] = asdict(takeoff.provenance)
        st.json(raw)

st.divider()
st.caption(
    "DCS simulation planning only. Not an approved real-world flight-performance source."
)
