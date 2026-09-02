from __future__ import annotations

from dataclasses import asdict, replace
from html import escape
import re

import pandas as pd
import streamlit as st

from src.f14perf.aircraft import (
    AircraftState,
    DEFAULT_CREW_OPERATING_ITEMS_LB,
    INTERNAL_FUEL_CAPACITY_LB,
)
from src.f14perf.airport import AirportDatabase
from src.f14perf.atmosphere import pressure_altitude_ft
from src.f14perf.authority import authority_registry
from src.f14perf.climb import ClimbModel
from src.f14perf.cruise import CruiseModel
from src.f14perf.engine import F110Deck
from src.f14perf.fuel import FuelModel
from src.f14perf.kneeboard import render_kneeboard_png, render_mission_card_pdf
from src.f14perf.landing import LandingModel
from src.f14perf.loadout import (
    STATION_ORDER,
    STORE_CATALOG,
    Loadout,
    loadout_from_preset,
    presets_for_variant,
    station_option_label,
    station_options,
)
from src.f14perf.takeoff import AutoTakeoffSelector, TakeoffModel
from src.f14perf.types import Environment, Runway, TakeoffInputs
from src.f14perf.weather import parse_metar, wind_components


st.set_page_config(page_title="F-14 EFB", page_icon="✈", layout="wide")
st.markdown(
    """
    <style>
    .block-container {padding-top: 1rem; padding-bottom: 2rem; max-width: 1450px;}
    [data-testid="stMetric"] {
        background: #0f2234;
        border: 1px solid #29445d;
        border-radius: 0.65rem;
        padding: 0.75rem 0.85rem;
    }
    [data-testid="stMetricValue"] {font-variant-numeric: tabular-nums;}
    [data-testid="stSidebar"] {border-right: 1px solid #20364a;}
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.25rem;
        overflow-x: auto;
        scrollbar-width: thin;
    }
    .stTabs [data-baseweb="tab"] {min-height: 2.8rem; white-space: nowrap;}
    .stButton button, .stDownloadButton button,
    [data-baseweb="select"] > div, [data-baseweb="input"] > div {
        min-height: 44px;
    }
    .efb-flow {
        color: #9fb3c8; font-size: 0.75rem; letter-spacing: 0.06em;
        margin-top: -0.35rem; margin-bottom: 0.6rem; white-space: nowrap;
        overflow-x: auto;
    }
    .aircraft-strip {
        position: sticky; top: 0.2rem; z-index: 50;
        display: grid; grid-template-columns: repeat(9, minmax(0, 1fr));
        gap: 1px; padding: 1px; margin: 0 0 0.8rem 0;
        border: 1px solid #29445d; border-radius: 0.65rem;
        background: #29445d; box-shadow: 0 4px 16px rgba(0,0,0,.24);
    }
    .aircraft-strip > div {background:#0b1b2a; padding:.48rem .55rem; min-width:0;}
    .aircraft-strip > div:first-child {border-radius:.55rem 0 0 .55rem;}
    .aircraft-strip > div:last-child {border-radius:0 .55rem .55rem 0;}
    .strip-label {font-size:.62rem; color:#89a3bb; letter-spacing:.06em; text-transform:uppercase;}
    .strip-value {font-size:.82rem; color:#f2f7fb; font-weight:650; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
    .result-kicker {color:#89a3bb; font-size:.72rem; letter-spacing:.08em; text-transform:uppercase;}
    .result-title {font-size:1.25rem; font-weight:700; margin-bottom:.55rem;}
    @media (max-width: 760px) {
        .block-container {padding: .65rem .65rem 1.5rem;}
        h1 {font-size:1.65rem !important;}
        .aircraft-strip {grid-template-columns: repeat(2, minmax(0, 1fr)); top:.1rem;}
        .aircraft-strip > div, .aircraft-strip > div:first-child, .aircraft-strip > div:last-child {border-radius:0;}
        [data-testid="stHorizontalBlock"] {flex-direction:column; gap:.5rem;}
        [data-testid="stHorizontalBlock"] > div {width:100% !important; min-width:100% !important;}
        [data-testid="stMetricValue"] {font-size:1.55rem;}
        .efb-flow {font-size:.67rem;}
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("F-14 Performance EFB")
st.caption("F-14B / F-14B(U) DCS mission planning")
st.markdown(
    '<div class="efb-flow">AIRCRAFT &gt; LOADOUT &gt; FUEL &gt; DEPARTURE &gt; TAKEOFF &gt; CLIMB &gt; CRUISE &gt; RECOVERY &gt; MISSION CARD</div>',
    unsafe_allow_html=True,
)

MODEL_REVISION = "2026-09-02-unified-aircraft-state"


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


def strip_item(label: str, value: str) -> str:
    return (
        "<div><div class='strip-label'>"
        + escape(label)
        + "</div><div class='strip-value' title='"
        + escape(value, quote=True)
        + "'>"
        + escape(value)
        + "</div></div>"
    )


st.sidebar.markdown("## Mission setup")
mission_name = st.sidebar.text_input("Mission / callsign", "vTF-77 Mission")

with st.sidebar.expander("1. Aircraft", expanded=True):
    aircraft_variant = st.selectbox("Variant", ["F-14B(U)", "F-14B"])

with st.sidebar.expander("2. DCS loadout", expanded=True):
    preset_options = [*presets_for_variant(aircraft_variant), "Custom station loadout"]
    loadout_preset = st.selectbox("Preset", preset_options)
    selected_stations: dict[str, str]
    if loadout_preset == "Custom station loadout":
        selected_stations = {}
        st.caption("Stations are ordered left glove to right glove, matching the DCS rearm logic.")
        for station in STATION_ORDER:
            options = station_options(station, aircraft_variant)
            selected_stations[station] = st.selectbox(
                f"STA {station}",
                options,
                format_func=lambda key, sta=station: station_option_label(sta, key),
                key=f"loadout_station_{station}",
            )
        try:
            launch_loadout = Loadout(selected_stations, variant=aircraft_variant)
        except ValueError as exc:
            st.error(str(exc))
            st.stop()
    else:
        launch_loadout = loadout_from_preset(loadout_preset, variant=aircraft_variant)
        selected_stations = launch_loadout.normalized_stations
    st.caption(launch_loadout.station_summary)

with st.sidebar.expander("3. Expected recovery stores", expanded=False):
    recovery_dispositions: dict[str, str] = {}
    loaded_recovery_stations = [
        station for station in STATION_ORDER if selected_stations.get(station, "EMPTY") != "EMPTY"
    ]
    if not loaded_recovery_stations:
        st.caption("Clean aircraft. No store disposition required.")
    for station in loaded_recovery_stations:
        store_id = selected_stations[station]
        store = STORE_CATALOG[store_id]
        choices = ["RETAIN"]
        if store.expendable:
            choices.append("EXPEND")
        if store.jettisonable:
            choices.append("JETTISON")
        recovery_dispositions[station] = st.selectbox(
            f"Recovery plan - STA {station}",
            choices,
            key=f"recovery_{station}_{store_id}",
            help=f"{station_option_label(station, store_id)}",
        )
    loadout = Loadout(
        selected_stations,
        variant=aircraft_variant,
        recovery_dispositions=recovery_dispositions,
    )
    if loaded_recovery_stations:
        st.caption(f"Planned store removal: {loadout.planned_removed_weight_lb:,.0f} lb")

with st.sidebar.expander("4. Fuel", expanded=True):
    internal_fuel = st.number_input(
        "Internal fuel (lb)",
        0,
        int(INTERNAL_FUEL_CAPACITY_LB),
        int(INTERNAL_FUEL_CAPACITY_LB),
        100,
    )
    external_capacity = float(loadout.external_fuel_capacity_lb)
    prior_capacity = float(st.session_state.get("_prior_external_capacity", 0.0))
    if prior_capacity != external_capacity:
        current_external = float(st.session_state.get("external_fuel_input", 0.0))
        if external_capacity <= 0:
            next_external = 0.0
        elif prior_capacity <= 0 or abs(current_external - prior_capacity) < 1.0:
            next_external = external_capacity
        else:
            next_external = min(current_external, external_capacity)
        st.session_state["external_fuel_input"] = next_external
        st.session_state["_prior_external_capacity"] = external_capacity
    external_fuel = st.number_input(
        "External fuel (lb)",
        0.0,
        external_capacity,
        step=100.0,
        key="external_fuel_input",
        disabled=external_capacity <= 0,
        help="Capacity follows the selected FPU-1 tanks. Removing or jettisoning tanks updates recovery capacity.",
    )
    st.caption(
        f"Launch fuel {internal_fuel + external_fuel:,.0f} lb | "
        f"capacity {INTERNAL_FUEL_CAPACITY_LB + external_capacity:,.0f} lb"
    )

with st.sidebar.expander("Advanced aircraft state", expanded=False):
    crew_items = st.number_input(
        "Crew / operating items (lb)",
        0,
        2_000,
        int(DEFAULT_CREW_OPERATING_ITEMS_LB),
        10,
        help="Project planning assumption until an authoritative DCS operating-weight delta is captured.",
    )
    provisional_aircraft = AircraftState(
        variant=aircraft_variant,
        loadout=loadout,
        internal_fuel_lb=float(internal_fuel),
        external_fuel_lb=float(external_fuel),
        crew_operating_items_lb=float(crew_items),
    )
    use_weight_override = st.checkbox(
        "Use DCS gross-weight override",
        help="Testing-only override. The adjustment remains tied to this state and carries into recovery.",
    )
    gross_weight_override = None
    if use_weight_override:
        gross_weight_override = st.number_input(
            "DCS gross-weight override (lb)",
            30_000,
            80_000,
            int(round(provisional_aircraft.calculated_launch_gross_weight_lb / 100.0) * 100),
            100,
        )

aircraft_base = AircraftState(
    variant=aircraft_variant,
    loadout=loadout,
    internal_fuel_lb=float(internal_fuel),
    external_fuel_lb=float(external_fuel),
    crew_operating_items_lb=float(crew_items),
    gross_weight_override_lb=None if gross_weight_override is None else float(gross_weight_override),
)

runway_entry_note = ""
departure_label = "MANUAL"
with st.sidebar.expander("5. Departure", expanded=True):
    runway_source = st.radio("Runway source", ["DCS airport database", "Manual"])
    runway_condition = st.selectbox("Runway condition", ["DRY", "WET"])
    if runway_source == "DCS airport database":
        db = airport_db(MODEL_REVISION)
        map_name = st.selectbox("DCS map", db.maps)
        airport = st.selectbox("Airfield", db.airports(map_name))
        runway_end = st.selectbox("Runway", db.runway_ends(map_name, airport))
        airport_selection = db.get(map_name, airport, runway_end, runway_condition)
        runway = airport_selection.runway
        landing_runway = runway
        departure_label = f"{airport} {runway_end}"
        entry_options = ["Full length"]
        if airport_selection.dcs_runway_start_tora_ft is not None:
            entry_options.insert(0, "DCS runway start")
        entry_options.append("Custom available distance")
        runway_entry = st.selectbox(
            "Runway entry",
            entry_options,
            help="Use the distance actually available from brake release.",
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
            f"HDG {runway.heading_deg:.0f} | TORA {runway.tora_ft:,.0f} | "
            f"TODA {runway.toda_ft:,.0f} | ASDA {runway.asda_ft:,.0f} ft"
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
with st.sidebar.expander("6. Weather", expanded=True):
    weather_mode = st.radio("Weather input", ["Manual", "METAR paste"])
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
                f"wind {('VRB' if parsed_environment.wind_dir_deg is None else f'{parsed_environment.wind_dir_deg:.0f}')} "
                f"at {parsed_environment.wind_speed_kt:.0f} kt"
            )
    if parsed_environment is None:
        oat = st.number_input("OAT (C)", -60.0, 60.0, 15.0, 1.0)
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

with st.sidebar.expander("7. Takeoff", expanded=True):
    flaps = st.selectbox("Takeoff flaps", ["UP", "MANEUVER", "FULL"])
    rating_options_by_flaps = {
        "UP": ["AUTO", "DERATE 3", "DERATE 2", "DERATE 1", "MIL"],
        "MANEUVER": ["AUTO", "DERATE 2", "DERATE 1", "MIL"],
        "FULL": ["AUTO", "MIL"],
    }
    power_setting = st.selectbox(
        "Takeoff thrust rating",
        rating_options_by_flaps[flaps],
        help="AUTO selects the lowest condition-calibrated discrete dry rating that clears the runway and AEO climb gates.",
    )
    if power_setting == "AUTO":
        st.caption("AUTO searches standardized dry ratings only. Afterburner is excluded.")
    else:
        field_elev_for_power = runway.elevation_ft
        if field_elev_for_power is None:
            field_elev_for_power = environment.field_elevation_ft
        takeoff_pa = pressure_altitude_ft(field_elev_for_power, environment.qnh_inhg)
        rating_preview = takeoff_engine().takeoff_rating(
            power_setting,
            takeoff_pa,
            environment.oat_c,
        )
        st.info(
            f"THRUST SET: {rating_preview.fuel_flow_pph_per_engine:,.0f} PPH / ENG | "
            f"RPM secondary: {rating_preview.rpm_reference}"
        )

with st.sidebar.expander("8. Mission and recovery", expanded=False):
    route_nm = st.number_input("Cruise leg distance (NM)", 0.0, 3_000.0, 300.0, 25.0)
    bingo = st.number_input("BINGO fuel (lb)", 0, 15_000, 4_000, 500)
    joker_margin = st.number_input("JOKER above BINGO (lb)", 0, 10_000, 2_000, 500)

with st.sidebar.expander("Advanced performance policy", expanded=False):
    runway_factor = st.number_input("Runway factor", 1.00, 1.50, 1.15, 0.01)
    climb_gate = st.number_input("Initial AEO climb gate (ft/NM)", 0, 1_000, 300, 25)
    wind_policy = st.radio("Takeoff wind policy", ["0% HW / 150% TW", "50% HW / 150% TW"])
    climb_choice = st.radio("Mission climb", ["MIL climb", "95% dry economy"])
    isa_delta = st.number_input("ISA deviation climb/cruise (C)", -30.0, 40.0, 0.0, 1.0)
    engineering_mode = st.checkbox("Engineering / data-audit mode")

headwind_credit = 0.0 if wind_policy.startswith("0%") else 50.0
climb_strategy = "MINIMUM_TIME" if climb_choice == "MIL climb" else "MOST_EFFICIENT"

inputs = TakeoffInputs(
    weight_lb=aircraft_base.launch_gross_weight_lb,
    environment=environment,
    runway=runway,
    flaps=flaps,
    thrust="AUTO" if power_setting == "AUTO" else "MANUAL",
    thrust_rating=None if power_setting == "AUTO" else power_setting,
    runway_factor=float(runway_factor),
    climb_target_ft_nm=float(climb_gate),
    headwind_credit_pct=headwind_credit,
    tailwind_penalty_pct=150.0,
    takeoff_loadout=loadout.station_summary,
)

m = models(MODEL_REVISION)
try:
    takeoff = m["takeoff_auto"].select(inputs)
    cruise = m["cruise"].optimum(
        aircraft_base.launch_gross_weight_lb,
        aircraft_base.launch_drag_index,
        isa_delta,
    )
    climb_profile = m["climb"].profile(
        aircraft_base.launch_gross_weight_lb,
        isa_delta_c=isa_delta,
        drag_index=aircraft_base.launch_drag_index,
        target_gradient_ft_nm=climb_gate,
        end_alt_ft=int(cruise.optimum_altitude_ft),
        strategy=climb_strategy,
    )
    climb_schedule = climb_profile.points
    fuel = m["fuel"].plan(
        aircraft_base.total_launch_fuel_lb,
        route_nm,
        climb_schedule,
        cruise,
        bingo,
        joker_margin,
    )
    aircraft = aircraft_base.with_recovery_fuel(max(0.0, fuel.landing_fuel_lb))
    landing = m["landing"].calculate(
        aircraft.expected_recovery_gross_weight_lb,
        environment,
        landing_runway,
        "DOWN",
        runway_factor,
        carrier_limit_lb=aircraft.definition.carrier_landing_limit_lb,
    )
    landing_fuel = m["landing"].fuel_reference(
        launch_zero_fuel_weight_lb=aircraft.launch_zero_fuel_weight_lb,
        recovery_zero_fuel_weight_lb=aircraft.recovery_zero_fuel_weight_lb,
        launch_fuel_capacity_lb=aircraft.launch_fuel_capacity_lb,
        recovery_fuel_capacity_lb=aircraft.recovery_fuel_capacity_lb,
        field_limit_lb=aircraft.definition.field_landing_limit_lb,
        carrier_limit_lb=aircraft.definition.carrier_landing_limit_lb,
    )
except Exception as exc:
    st.error(f"Performance model error: {exc}")
    st.stop()

headwind, crosswind = wind_components(
    environment.wind_dir_deg,
    environment.wind_speed_kt,
    runway.heading_deg,
)
takeoff_status = (
    "PLANNING HOLD"
    if not takeoff.takeoff_data_valid
    else ("REFERENCE ONLY" if takeoff.feasible else "LIMIT EXCEEDED")
)

advisories = [
    *aircraft.warnings,
    *weather_notes,
    *takeoff.warnings,
    *landing.warnings,
    *fuel.warnings,
]
if fuel.landing_fuel_lb > aircraft.recovery_fuel_capacity_lb:
    advisories.append(
        "Mission fuel result exceeds the fuel capacity retained for recovery; expected recovery fuel was limited to retained capacity."
    )
if aircraft.expected_recovery_gross_weight_lb > aircraft.definition.carrier_landing_limit_lb:
    advisories.append(
        f"Expected recovery weight exceeds the {aircraft.definition.carrier_landing_limit_lb:,.0f} lb carrier limit for {aircraft.variant}."
    )
advisories = list(dict.fromkeys(note for note in advisories if note))

strip_html = "".join(
    [
        strip_item("Variant", aircraft.variant),
        strip_item("Config", aircraft.config_id),
        strip_item("Launch GW", f"{aircraft.launch_gross_weight_lb:,.0f} LB"),
        strip_item("Fuel", f"{aircraft.total_launch_fuel_lb:,.0f} LB"),
        strip_item("Loadout", aircraft.loadout.compact_summary),
        strip_item("Drag", aircraft.drag_state),
        strip_item("Thrust", f"{takeoff.thrust_setting} / {takeoff.fuel_flow_pph_per_engine:,.0f} PPH"),
        strip_item("Departure", departure_label),
        strip_item("Recovery", f"{aircraft.expected_recovery_gross_weight_lb:,.0f} LB"),
    ]
)
st.markdown(f'<div class="aircraft-strip">{strip_html}</div>', unsafe_allow_html=True)

summary1, summary2, summary3, summary4 = st.columns(4)
summary1.metric("Departure", takeoff_status, departure_label)
summary2.metric(
    "SET FF / engine",
    f"{takeoff.fuel_flow_pph_per_engine:,.0f} PPH",
    f"{takeoff.thrust_setting} | PRIMARY",
)
summary3.metric("Launch gross weight", f"{aircraft.launch_gross_weight_lb:,.0f} lb", aircraft.config_id)
summary4.metric(
    "Expected recovery weight",
    f"{aircraft.expected_recovery_gross_weight_lb:,.0f} lb",
    f"fuel {aircraft.expected_recovery_fuel_lb:,.0f} lb",
)

tab_names = ["Overview", "Takeoff", "Climb", "Cruise", "Recovery", "Mission Card"]
if engineering_mode:
    tab_names.extend(["Engineering", "Data audit"])
tabs = st.tabs(tab_names)
overview_tab, takeoff_tab, climb_tab, cruise_tab, recovery_tab, card_tab = tabs[:6]
engineering_tab = tabs[6] if engineering_mode else None
data_tab = tabs[7] if engineering_mode else None

with overview_tab:
    st.markdown(
        f'<div class="result-kicker">{escape(runway.name)}</div><div class="result-title">TAKEOFF PERFORMANCE</div>',
        unsafe_allow_html=True,
    )
    if takeoff_status == "PLANNING HOLD":
        st.warning("Planning hold. Selected conditions include an unvalidated performance domain.")
    elif takeoff_status == "LIMIT EXCEEDED":
        st.error("The selected runway or climb planning limit is exceeded.")
    else:
        st.info("Reference only. Legacy runway data are not a takeoff clearance or GO decision.")

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("GW", f"{aircraft.launch_gross_weight_lb:,.0f} LB")
    r2.metric("CONFIG", takeoff.flaps)
    r3.metric("THRUST", f"{takeoff.fuel_flow_pph_per_engine:,.0f} PPH / ENG", takeoff.thrust_setting)
    r4.metric("RPM cross-check", takeoff.rpm_reference, "SECONDARY")
    v1, v2, v3, v4 = st.columns(4)
    v1.metric("V1", "WITHHELD", "engine-cut validation required")
    v2.metric("VR", f"{takeoff.vr_kt:.0f}")
    v3.metric("V2", f"{takeoff.v2_kt:.0f}")
    v4.metric("TRIM", f"{takeoff.stabilizer_trim_anu:.1f} ANU", "DCS TRIAL")
    d1, d2, d3 = st.columns(3)
    d1.metric("TODR reference", f"{takeoff.factored_agd_ft:,.0f} FT", "legacy factored")
    d2.metric("RUNWAY", f"{runway.toda_ft:,.0f} FT")
    d3.metric("MARGIN", f"{takeoff.toda_margin_ft:+,.0f} FT")
    st.caption(
        "Set fuel flow per engine first. RPM is an atmospheric cross-check and does not represent identical thrust in every condition."
    )

    if advisories:
        with st.expander(f"Planning notes ({len(advisories)})"):
            for note in advisories:
                st.write(f"- {note}")

    st.subheader("Aircraft state")
    a1, a2, a3 = st.columns(3)
    a1.metric("Zero-fuel weight", f"{aircraft.launch_zero_fuel_weight_lb:,.0f} lb")
    a2.metric("Stores and adapters", f"{loadout.launch_payload_weight_lb:,.0f} lb", "nominal where flagged")
    a3.metric("Mission fuel", f"{aircraft.total_launch_fuel_lb:,.0f} lb")
    st.caption(loadout.station_summary)

with takeoff_tab:
    st.subheader("Takeoff")
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Flaps", takeoff.flaps)
    p2.metric("SET FF / engine", f"{takeoff.fuel_flow_pph_per_engine:,.0f} PPH", "PRIMARY")
    p3.metric("RPM cross-check", takeoff.rpm_reference, "SECONDARY")
    p4.metric("Rating", takeoff.thrust_setting)
    st.caption(
        "Set the displayed FF per engine first. Verify matched indications. RPM and nozzle position are secondary cross-checks."
    )
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("V1", "WITHHELD", "no engine-cut matrix")
    s2.metric("Vr reference", f"{takeoff.vr_kt:.0f} KIAS")
    s3.metric("V2 reference", f"{takeoff.v2_kt:.0f} KIAS")
    s4.metric("Vfs estimate", f"{takeoff.vfs_kt:.0f} KIAS")
    tr1, tr2, tr3 = st.columns(3)
    tr1.metric("Pre-roll trial trim", f"{takeoff.stabilizer_trim_anu:.1f} ANU")
    tr2.metric("OEI target", f"{takeoff.oei_climb_speed_kt:.0f} KIAS", "V2 + 15 / gear up")
    tr3.metric("OEI power", "MIL", "operating engine")
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Legacy ASD", f"{takeoff.factored_asd_ft:,.0f} ft", "factored")
    d2.metric("Legacy AEO distance", f"{takeoff.factored_agd_ft:,.0f} ft", "factored")
    d3.metric("ASDA margin", f"{takeoff.asda_margin_ft:+,.0f} ft")
    d4.metric("TODA margin", f"{takeoff.toda_margin_ft:+,.0f} ft")
    source_block(takeoff.provenance, takeoff.notes)

with climb_tab:
    st.subheader(f"Climb planning hold to FL{cruise.flight_level:03d}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Schedule", "250 / 300 / M0.72", "DCS test schedule")
    c2.metric("Time allowance", f"{climb_profile.time_min:.0f} min")
    c3.metric("Distance allowance", f"{climb_profile.distance_nm:,.0f} NM")
    c4.metric("Fuel allowance", f"{climb_profile.fuel_burn_lb:,.0f} lb")
    st.warning(
        "PLANNING HOLD. The required NATOPS performance-supplement charts and matched Tacview climb matrix are not yet in the production model."
    )
    for point in checkpoint_rows(climb_schedule):
        with st.expander(f"{point.altitude_ft:,.0f} ft | {point.ias_kt:.0f} KIAS | {point.roc_fpm:,.0f} fpm"):
            st.write(
                f"TAS {point.tas_kt:.0f} kt | RPM {point.rpm_pct:.0f}% | "
                f"FF {point.fuel_flow_pph_per_engine:,.0f} PPH/engine | "
                f"gradient {point.gradient_ft_nm:,.0f} ft/NM"
            )
    source_block(climb_profile.provenance, climb_profile.notes)

with cruise_tab:
    st.subheader("Cruise planning hold")
    cr1, cr2, cr3, cr4 = st.columns(4)
    cr1.metric("Trial flight level", f"FL{cruise.flight_level:03d}")
    cr2.metric("Trial speed", f"{cruise.optimum_ias_kt:.0f} KIAS", f"M {cruise.optimum_mach:.2f}")
    cr3.metric("Trial FF / engine", f"{cruise.fuel_flow_pph_per_engine:,.0f} PPH")
    cr4.metric("RPM cross-check", f"~{cruise.rpm_pct:.0f}%", "uncalibrated")
    st.warning(
        "PLANNING HOLD. Cruise altitude, schedule, FF, RPM, range, and endurance require NATOPS reconstruction and controlled DCS calibration."
    )
    source_block(cruise.provenance, cruise.notes)

with recovery_tab:
    st.subheader("Expected recovery")
    l1, l2, l3, l4 = st.columns(4)
    l1.metric("Recovery gross weight", f"{aircraft.expected_recovery_gross_weight_lb:,.0f} lb")
    l2.metric("Recovery fuel", f"{aircraft.expected_recovery_fuel_lb:,.0f} lb")
    l3.metric("Recovery stores", f"{loadout.recovery_payload_weight_lb:,.0f} lb")
    l4.metric("Recovery drag", f"{aircraft.recovery_drag_index:.0f}", "internal, guarded")
    st.caption(loadout.recovery_summary)

    st.subheader("Field landing")
    f1, f2, f3, f4 = st.columns(4)
    f1.metric("On-speed reference", "15 units AOA")
    f2.metric("DLC neutral", f"~{landing.on_speed_ias_est_kt:.0f} KIAS", f"+/-{landing.on_speed_ias_tolerance_kt:.0f}")
    f3.metric("Factored distance", f"{landing.factored_distance_ft:,.0f} ft", "legacy grid")
    f4.metric("Runway margin", f"{landing.runway_margin_ft:+,.0f} ft")

    st.subheader("Maximum recovery fuel")
    rf1, rf2 = st.columns(2)
    rf1.metric(
        f"Field limit {landing_fuel.field_limit_lb:,.0f} lb",
        f"{landing_fuel.field_expended_fuel_lb:,.0f} lb fuel",
        "expected store disposition",
    )
    rf2.metric(
        f"Carrier limit {landing_fuel.carrier_limit_lb:,.0f} lb",
        f"{landing_fuel.carrier_expended_fuel_lb:,.0f} lb fuel",
        aircraft.variant,
    )
    source_block(landing_fuel.provenance, landing_fuel.notes)
    source_block(landing.provenance)

kneeboard_rpm_crosscheck = takeoff.rpm_reference.replace(" N2", "")
kneeboard_sections = [
    (
        "Aircraft",
        [
            f"{aircraft.variant} | CONFIG {aircraft.config_id} | LAUNCH GW {aircraft.launch_gross_weight_lb:,.0f} LB",
            f"FUEL {aircraft.total_launch_fuel_lb:,.0f} LB | LOADOUT {loadout.compact_summary}",
        ],
    ),
    (
        "Departure",
        [
            f"{runway.name} | {headwind:+.0f} KT HW | {abs(crosswind):.0f} KT XW",
            f"PA {takeoff.pressure_altitude_ft:,.0f} FT | OAT {environment.oat_c:.0f} C | QNH {environment.qnh_inhg:.2f} | {runway.condition}",
        ],
    ),
    (
        "Takeoff",
        [
            f"{takeoff.flaps} | {takeoff.thrust_setting} | TRIM TRIAL {takeoff.stabilizer_trim_anu:.1f} ANU | {takeoff_status}",
            f"SET {takeoff.fuel_flow_pph_per_engine:,.0f} PPH/ENG PRIMARY | RPM X-CHECK {kneeboard_rpm_crosscheck}",
            f"V1 WITHHELD | VR REF {takeoff.vr_kt:.0f} | V2 REF {takeoff.v2_kt:.0f} | OEI {takeoff.oei_climb_speed_kt:.0f} KIAS",
            f"AEO DIST {takeoff.factored_agd_ft:,.0f} | RUNWAY {runway.toda_ft:,.0f} | MARGIN {takeoff.toda_margin_ft:+,.0f} FT",
        ],
    ),
    (
        "Climb planning hold",
        [
            "DCS TEST SCHEDULE 250 KIAS TO 10K, THEN 300 KIAS TO M0.72",
            f"FL{cruise.flight_level:03d} | {climb_profile.time_min:.0f} MIN | {climb_profile.distance_nm:.0f} NM | {climb_profile.fuel_burn_lb:,.0f} LB",
        ],
    ),
    (
        "Cruise planning hold",
        [
            f"FL{cruise.flight_level:03d} | {cruise.optimum_ias_kt:.0f} KIAS / M{cruise.optimum_mach:.2f}",
            f"{cruise.fuel_flow_pph_per_engine:,.0f} PPH/ENG | RPM X-CHECK ~{cruise.rpm_pct:.0f}%",
        ],
    ),
    (
        "Recovery",
        [
            f"GW {aircraft.expected_recovery_gross_weight_lb:,.0f} LB | FUEL {aircraft.expected_recovery_fuel_lb:,.0f} LB | 15 AOA",
            f"DLC NEUTRAL ~{landing.on_speed_ias_est_kt:.0f} +/-{landing.on_speed_ias_tolerance_kt:.0f} KIAS",
            f"STORES: {loadout.recovery_summary}",
        ],
    ),
    (
        "Fuel",
        [
            f"START {aircraft.total_launch_fuel_lb:,.0f} | PLAN BURN {fuel.mission_burn_lb:,.0f} | LAND {fuel.landing_fuel_lb:,.0f} LB",
            f"JOKER {fuel.joker_lb:,.0f} | BINGO {fuel.bingo_lb:,.0f} LB",
        ],
    ),
]
kneeboard_png = render_kneeboard_png(
    mission_name or "vTF-77 Mission",
    f"{aircraft.variant} | {aircraft.config_id} | {MODEL_REVISION}",
    kneeboard_sections,
    footer=f"DCS ONLY | TAKEOFF {takeoff_status} | CLIMB/CRUISE/FUEL HOLD",
)
kneeboard_pdf = render_mission_card_pdf(
    mission_name or "vTF-77 Mission",
    f"{aircraft.variant} | {aircraft.config_id} | {MODEL_REVISION}",
    kneeboard_sections,
    footer=f"DCS ONLY | TAKEOFF {takeoff_status} | CLIMB/CRUISE/FUEL HOLD",
)

with card_tab:
    st.subheader("Mission card")
    kb1, kb2 = st.columns([1, 1])
    with kb1:
        st.image(kneeboard_png, caption="768 x 1024 DCS kneeboard")
    with kb2:
        st.write(f"**Aircraft state:** {aircraft.config_id}")
        st.write(f"**Launch:** {aircraft.launch_gross_weight_lb:,.0f} lb, {loadout.compact_summary}")
        st.write(f"**Recovery:** {aircraft.expected_recovery_gross_weight_lb:,.0f} lb, {loadout.recovery_summary}")
        safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", mission_name).strip("_") or "F14_EFB"
        st.download_button(
            "Download kneeboard PNG",
            data=kneeboard_png,
            file_name=f"{safe_name}_kneeboard.png",
            mime="image/png",
            type="primary",
        )
        st.download_button(
            "Download printable PDF",
            data=kneeboard_pdf,
            file_name=f"{safe_name}_mission_card.pdf",
            mime="application/pdf",
        )
        st.caption("Both exports update from the same aircraft state as every performance page.")

if engineering_mode and engineering_tab is not None:
    with engineering_tab:
        st.subheader("Engineering detail")
        st.caption("These values are removed from the normal pilot workflow.")
        st.write("**Weight breakdown**")
        for label, value in aircraft.weight_breakdown.items():
            st.write(f"{label}: {value:,.0f} lb")
        st.write("**Raw takeoff result**")
        raw = asdict(takeoff)
        raw.pop("fuel_flow_pph_total", None)
        raw["provenance"] = asdict(takeoff.provenance)
        st.json(raw)
        st.write("**Structured store catalog**")
        store_rows = []
        for store_id, store in STORE_CATALOG.items():
            if store_id == "EMPTY":
                continue
            compatible = [
                station for station in STATION_ORDER if store.supports(station, aircraft_variant)
            ]
            store_rows.append(
                {
                    "Store": store.label,
                    "Stations": ", ".join(compatible),
                    "Nominal unit lb": store.nominal_store_weight_lb,
                    "Adapter lb": store.adapter_weight_lb,
                    "Weight source": store.weight_source_class,
                    "Drag source": store.drag_source_class,
                }
            )
        st.dataframe(pd.DataFrame(store_rows), width="stretch", hide_index=True)

if engineering_mode and data_tab is not None:
    with data_tab:
        st.subheader("Production model authority")
        authorities = authority_registry()
        authority_rows = [asdict(authority) for authority in authorities.values()]
        st.dataframe(pd.DataFrame(authority_rows), width="stretch", hide_index=True)
        st.subheader("Validation evidence")
        with st.expander("DCS engine observations"):
            st.dataframe(pd.read_csv("data/dcs_engine_observations.csv"), width="stretch", hide_index=True)
        with st.expander("Discrete takeoff rating database"):
            st.dataframe(takeoff_engine().takeoff_ratings, width="stretch", hide_index=True)
        with st.expander("Maintained validation scenarios"):
            st.dataframe(pd.read_csv("data/validation_scenarios.csv"), width="stretch", hide_index=True)
        with st.expander("Attached Tacview takeoff motion"):
            st.dataframe(pd.read_csv("data/tacview_takeoff_motion.csv"), width="stretch", hide_index=True)

st.divider()
st.caption("DCS simulation planning only. Not an approved real-world flight-performance source.")
