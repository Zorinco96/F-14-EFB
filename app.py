from __future__ import annotations

from dataclasses import asdict

import pandas as pd
import streamlit as st

from src.f14perf.airport import AirportDatabase
from src.f14perf.climb import ClimbModel
from src.f14perf.cruise import CruiseModel
from src.f14perf.energy import EnergyModel
from src.f14perf.fuel import FuelModel
from src.f14perf.landing import LandingModel
from src.f14perf.mission import MissionPlanner
from src.f14perf.takeoff import AutoTakeoffSelector, TakeoffModel
from src.f14perf.types import Environment, Runway, TakeoffInputs
from src.f14perf.weather import parse_metar, wind_components


st.set_page_config(page_title="F-14 EFB", page_icon="✈", layout="wide")
st.title("F-14 EFB")
st.caption("DCS World planning model • v3 • provenance-aware performance calculations")


@st.cache_resource
def airport_db():
    return AirportDatabase()


@st.cache_resource
def models():
    return {
        "takeoff_auto": AutoTakeoffSelector(),
        "takeoff": TakeoffModel(),
        "climb": ClimbModel(),
        "cruise": CruiseModel(),
        "landing": LandingModel(),
        "energy": EnergyModel(),
        "fuel": FuelModel(),
        "mission": MissionPlanner(),
    }


def prov_caption(prov):
    st.caption(f"Source method: **{prov.label}** | {prov.source} | {prov.confidence}")
    if prov.detail:
        st.caption(prov.detail)


def runway_inputs() -> Runway:
    source = st.sidebar.radio("Runway source", ["DCS airport database", "Manual"], horizontal=False)
    condition = st.sidebar.selectbox("Runway condition", ["DRY", "WET"])
    if source == "DCS airport database":
        db = airport_db()
        map_name = st.sidebar.selectbox("DCS map", db.maps)
        airport = st.sidebar.selectbox("Airfield", db.airports(map_name))
        runway_end = st.sidebar.selectbox("Runway", db.runway_ends(map_name, airport))
        selection = db.get(map_name, airport, runway_end, condition)
        r = selection.runway
        st.sidebar.caption(
            f"HDG {r.heading_deg:.0f}° | TORA {r.tora_ft:.0f} | TODA {r.toda_ft:.0f} | ASDA {r.asda_ft:.0f} ft"
        )
        if r.notes:
            st.sidebar.caption(f"DB note: {r.notes}")
        return r

    heading = st.sidebar.number_input("Runway heading (deg)", 0.0, 360.0, 0.0, 1.0)
    tora = st.sidebar.number_input("TORA (ft)", 500.0, 20000.0, 8000.0, 100.0)
    toda = st.sidebar.number_input("TODA (ft)", 500.0, 25000.0, float(tora), 100.0)
    asda = st.sidebar.number_input("ASDA (ft)", 500.0, 25000.0, float(tora), 100.0)
    elev = st.sidebar.number_input("Threshold elevation (ft)", -1500.0, 15000.0, 0.0, 100.0)
    slope = st.sidebar.number_input("Runway slope (%)", -5.0, 5.0, 0.0, 0.1)
    return Runway(
        name="Manual runway",
        heading_deg=heading,
        tora_ft=tora,
        toda_ft=toda,
        asda_ft=asda,
        slope_pct=slope,
        condition=condition,
        elevation_ft=elev,
    )


def environment_inputs(runway: Runway) -> Environment:
    mode = st.sidebar.radio("Weather input", ["Manual", "METAR paste"])
    default_elev = runway.elevation_ft if runway.elevation_ft is not None else 0.0
    if mode == "METAR paste":
        raw = st.sidebar.text_area("Paste METAR", placeholder="KLSV 152355Z 22012G20KT 10SM FEW100 35/08 A2985")
        if raw.strip():
            parsed = parse_metar(raw, default_elev)
            e = parsed.environment
            st.sidebar.caption(
                f"Parsed: OAT {e.oat_c:.0f} C | QNH {e.qnh_inhg:.2f} | wind "
                f"{('VRB' if e.wind_dir_deg is None else f'{e.wind_dir_deg:.0f}°')} {e.wind_speed_kt:.0f} kt"
            )
            for n in parsed.notes:
                st.sidebar.warning(n)
            return e
        st.sidebar.info("Paste a METAR to populate weather. Defaults are active until then.")

    oat = st.sidebar.number_input("OAT (°C)", -60.0, 60.0, 15.0, 1.0)
    qnh = st.sidebar.number_input("QNH (inHg)", 27.00, 31.50, 29.92, 0.01)
    wind_dir = st.sidebar.number_input("Wind direction (deg true/mag as used for runway)", 0.0, 360.0, 0.0, 10.0)
    wind_speed = st.sidebar.number_input("Wind speed (kt)", 0.0, 80.0, 0.0, 1.0)
    return Environment(
        field_elevation_ft=default_elev,
        oat_c=oat,
        qnh_inhg=qnh,
        wind_dir_deg=wind_dir if wind_speed > 0 else None,
        wind_speed_kt=wind_speed,
    )


st.sidebar.header("Aircraft / Mission")
takeoff_weight = st.sidebar.number_input("Takeoff gross weight (lb)", 40000, 76000, 65000, 500)
landing_weight = st.sidebar.number_input("Landing gross weight (lb)", 40000, 76000, 54000, 500)
starting_fuel = st.sidebar.number_input("Starting fuel (lb)", 0, 21000, 16000, 500)
drag_index = st.sidebar.number_input("Drag index", 0.0, 200.0, 0.0, 5.0)
route_nm = st.sidebar.number_input("Planned route distance (NM)", 0.0, 3000.0, 300.0, 25.0)

st.sidebar.header("Runway")
runway = runway_inputs()
st.sidebar.header("Weather")
environment = environment_inputs(runway)

st.sidebar.header("Takeoff policy")
flaps = st.sidebar.selectbox("Takeoff flaps", ["AUTO", "UP", "MANEUVER", "FULL"])
thrust_mode = st.sidebar.selectbox("Takeoff thrust", ["AUTO", "MANUAL"])
rpm = None
if thrust_mode == "MANUAL":
    rpm = st.sidebar.slider("Takeoff RPM (%)", 85, 100, 100)
runway_factor = st.sidebar.number_input("Runway planning factor", 1.00, 1.50, 1.10, 0.01)
climb_gate = st.sidebar.number_input("AEO climb gate (ft/NM)", 0, 1000, 300, 25)
wind_policy = st.sidebar.radio(
    "Takeoff wind credit",
    ["50% HW / 150% TW", "0% HW / 150% TW"],
    help="The selected credit is applied to takeoff runway calculations only.",
)
headwind_credit = 50.0 if wind_policy.startswith("50%") else 0.0
tailwind_penalty = 150.0

st.sidebar.header("Climb policy")
climb_strategy_label = st.sidebar.radio(
    "Climb profile",
    ["Most Efficient", "Minimum Time (MIL)"],
    help=(
        "Most Efficient uses the lowest dry RPM meeting the gradient gate. "
        "Minimum Time uses 100% dry MIL and maximizes modeled rate of climb."
    ),
)
climb_strategy = (
    "MOST_EFFICIENT" if climb_strategy_label == "Most Efficient" else "MINIMUM_TIME"
)
isa_delta = st.sidebar.number_input("ISA deviation for climb/cruise (°C)", -30.0, 40.0, 0.0, 1.0)

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
    tailwind_penalty_pct=tailwind_penalty,
)

m = models()

try:
    takeoff = m["takeoff_auto"].select(inputs)
    climb_profiles = m["climb"].profiles(
        takeoff_weight, isa_delta_c=isa_delta, drag_index=drag_index, target_gradient_ft_nm=climb_gate
    )
    climb_profile = climb_profiles[climb_strategy]
    climb_schedule = climb_profile.points
    cruise = m["cruise"].optimum(takeoff_weight, drag_index, isa_delta)
    landing = m["landing"].calculate(landing_weight, environment, runway, "DOWN", runway_factor)
except Exception as exc:
    st.error(f"Performance model error: {exc}")
    st.stop()

headwind, crosswind = wind_components(environment.wind_dir_deg, environment.wind_speed_kt, runway.heading_deg)

summary1, summary2, summary3, summary4 = st.columns(4)
summary1.metric("Takeoff", "GO" if takeoff.feasible else "NO-GO")
summary2.metric("Config / Thrust", f"{takeoff.flaps} / {takeoff.thrust_setting}")
summary3.metric("Runway wind", f"{headwind:+.0f} kt HW", f"{abs(crosswind):.0f} kt XW")
summary4.metric("Optimum cruise", f"M {cruise.optimum_mach:.3f}", f"FL{cruise.optimum_altitude_ft/100:.0f}")

mission_tab, takeoff_tab, climb_tab, cruise_tab, landing_tab, energy_tab, data_tab = st.tabs(
    ["Mission Card", "Takeoff", "Climb", "Cruise", "Landing", "Energy", "Data & Sources"]
)

with takeoff_tab:
    if takeoff.feasible:
        st.success("TAKEOFF PERFORMANCE: planning criteria satisfied")
    else:
        st.error("TAKEOFF PERFORMANCE: one or more planning criteria not satisfied")
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Flaps", takeoff.flaps)
    p2.metric("Thrust", takeoff.thrust_setting)
    p3.metric("Engine target", f"{takeoff.rpm_pct:.0f}% N2")
    p4.metric("FF reference", f"{takeoff.fuel_flow_pph_per_engine:,.0f} pph / engine")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("V1", f"{takeoff.v1_kt:.0f} kt", f"table ref {takeoff.v1_reference_kt:.0f}")
    c2.metric("Vr", f"{takeoff.vr_kt:.0f} kt")
    c3.metric("V2", f"{takeoff.v2_kt:.0f} kt")
    c4.metric("Vfs", f"{takeoff.vfs_kt:.0f} kt")
    st.caption(f"Vs reference: {takeoff.vs_kt:.0f} KIAS")
    t1, t2, t3 = st.columns(3)
    trim_delta = (
        f"DCS BAND {takeoff.stabilizer_trim_band_anu[0]:.1f}-{takeoff.stabilizer_trim_band_anu[1]:.1f}"
        if takeoff.stabilizer_trim_band_anu
        else "SET BEFORE ROLL"
    )
    t1.metric(
        "Takeoff pitch trim",
        f"{takeoff.stabilizer_trim_anu:.1f} ANU",
        trim_delta,
    )
    t2.metric(
        "OEI climb speed",
        f"{takeoff.oei_climb_speed_kt:.0f} KIAS",
        "V2 + 15",
    )
    t3.metric("OEI configuration", "GEAR UP / MIL", "OPERATING ENGINE")
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("ASD", f"{takeoff.asd_ft:.0f} ft", f"factored {takeoff.factored_asd_ft:.0f}")
    d2.metric("AGD", f"{takeoff.agd_ft:.0f} ft", f"factored {takeoff.factored_agd_ft:.0f}")
    d3.metric("ASDA margin", f"{takeoff.asda_margin_ft:+.0f} ft")
    d4.metric("TODA margin", f"{takeoff.toda_margin_ft:+.0f} ft")
    g1, g2, g3, g4 = st.columns(4)
    g1.metric("AEO climb", f"{takeoff.climb_gradient_ft_nm:.0f} ft/NM")
    g2.metric("OEI advisory", f"{takeoff.climb_gradient_oei_ft_nm:.0f} ft/NM")
    g3.metric("Pressure altitude", f"{takeoff.pressure_altitude_ft:.0f} ft")
    g4.metric(
        "Wind used",
        f"{takeoff.credited_headwind_kt:+.1f} kt",
        f"raw {takeoff.headwind_kt:+.1f} kt",
    )
    st.info(
        f"Pre-roll stabilator trim: {takeoff.stabilizer_trim_anu:.1f} ANU. "
        f"{takeoff.stabilizer_trim_note}"
    )
    for warning in takeoff.warnings:
        st.warning(warning)
    prov_caption(takeoff.provenance)
    with st.expander("Takeoff model notes"):
        for note in takeoff.notes:
            st.write(f"• {note}")

with climb_tab:
    st.subheader(f"{climb_profile.label}: 1,000 to 10,000 ft")
    efficient_profile = climb_profiles["MOST_EFFICIENT"]
    minimum_time_profile = climb_profiles["MINIMUM_TIME"]
    cp1, cp2, cp3, cp4 = st.columns(4)
    cp1.metric("Efficient time", f"{efficient_profile.time_min:.2f} min")
    cp2.metric("Efficient fuel", f"{efficient_profile.fuel_burn_lb:,.0f} lb")
    cp3.metric("Min-time time", f"{minimum_time_profile.time_min:.2f} min")
    cp4.metric("Min-time fuel", f"{minimum_time_profile.fuel_burn_lb:,.0f} lb")
    st.caption(
        "Both profiles search 190–250 KIAS and retain the 250 KIAS ceiling. "
        "The comparison is model-relative and is not a released F-14B climb chart."
    )
    climb_df = pd.DataFrame([
        {
            "Altitude ft": p.altitude_ft,
            "IAS kt": p.ias_kt,
            "TAS kt": p.tas_kt,
            "RPM %": p.rpm_pct,
            "ROC fpm": p.roc_fpm,
            "Gradient ft/NM": p.gradient_ft_nm,
            "Fuel flow pph": p.fuel_flow_pph_total,
            "Method": p.provenance.label,
        }
        for p in climb_schedule
    ])
    st.dataframe(climb_df, width="stretch", hide_index=True)
    for note in climb_profile.notes:
        if climb_profile.unmet_segments and "cannot meet" in note:
            st.warning(note)
        else:
            st.write(f"• {note}")
    prov_caption(climb_profile.provenance)

with cruise_tab:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Optimum altitude", f"{cruise.optimum_altitude_ft:.0f} ft")
    c2.metric("Optimum Mach", f"{cruise.optimum_mach:.3f}")
    c3.metric("TAS", f"{cruise.tas_kt:.0f} kt")
    c4.metric("Estimated fuel flow", f"{cruise.fuel_flow_pph_total:.0f} pph")
    c5, c6 = st.columns(2)
    c5.metric("Specific range", f"{cruise.specific_range_nm_per_1000lb:.2f} NM/1000 lb")
    c6.metric("Endurance", f"{cruise.endurance_hr_per_1000lb:.3f} hr/1000 lb")
    prov_caption(cruise.provenance)
    for note in cruise.notes:
        st.write(f"• {note}")

with landing_tab:
    l1, l2, l3, l4 = st.columns(4)
    l1.metric("Ground roll", f"{landing.ground_roll_ft:.0f} ft")
    l2.metric("Factored roll", f"{landing.factored_distance_ft:.0f} ft")
    l3.metric("Runway margin", f"{landing.runway_margin_ft:+.0f} ft")
    l4.metric("On-speed", f"15 units AOA", f"~{landing.on_speed_ias_est_kt:.0f} KIAS est")
    for warning in landing.warnings:
        st.warning(warning)
    prov_caption(landing.provenance)
    st.caption("Carrier reference: Heatblur documents a 54,000 lb maximum carrier landing weight for F-14B(U) loadout planning.")

with energy_tab:
    st.subheader("Energy / maneuver estimate")
    e1, e2, e3, e4 = st.columns(4)
    energy_alt = e1.number_input("Altitude (ft)", 0, 50000, 10000, 1000)
    energy_ias = e2.number_input("IAS (kt)", 120, 800, 350, 10)
    g_limit = e3.number_input("Planning G limit", 1.5, 10.0, 6.5, 0.5, help="User planning input, not asserted as a NATOPS structural limit.")
    power = e4.selectbox("Power", ["MIL", "AB"])
    energy = m["energy"].calculate(takeoff_weight, energy_alt, energy_ias, drag_index, g_limit, power, isa_delta)
    q1, q2, q3 = st.columns(3)
    q1.metric("Specific excess power", f"{energy.ps_fps:+.0f} ft/s")
    q2.metric("Instantaneous", f"{energy.instantaneous_turn_rate_dps:.1f}°/s", f"{energy.instantaneous_g:.2f} G")
    q3.metric("Sustained", f"{energy.sustained_turn_rate_dps:.1f}°/s", f"{energy.sustained_g:.2f} G")
    r1, r2 = st.columns(2)
    r1.metric("Instantaneous radius", f"{energy.instantaneous_radius_ft:.0f} ft")
    r2.metric("Sustained radius", f"{energy.sustained_radius_ft:.0f} ft")
    prov_caption(energy.provenance)

with mission_tab:
    bingo = st.number_input("BINGO fuel (lb)", 0, 15000, 4000, 500)
    joker_margin = st.number_input("JOKER above BINGO (lb)", 0, 10000, 2000, 500)
    fuel = m["fuel"].plan(starting_fuel, route_nm, climb_schedule, cruise, bingo, joker_margin)
    st.subheader("Mission Card")
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("TO config", f"{takeoff.flaps} / {takeoff.thrust_setting}")
    mc2.metric(
        "V1 / Vr / V2 / Vfs",
        f"{takeoff.v1_kt:.0f} / {takeoff.vr_kt:.0f} / "
        f"{takeoff.v2_kt:.0f} / {takeoff.vfs_kt:.0f}",
    )
    mc3.metric("Engine target", f"{takeoff.rpm_pct:.0f}% N2 / {takeoff.fuel_flow_pph_per_engine:,.0f} FF")
    mc4.metric("AEO climb", f"{takeoff.climb_gradient_ft_nm:.0f} ft/NM")
    mt1, mt2, mt3 = st.columns(3)
    mt1.metric("Takeoff trim", f"{takeoff.stabilizer_trim_anu:.1f} ANU", trim_delta)
    mt2.metric("OEI speed", f"{takeoff.oei_climb_speed_kt:.0f} KIAS", "V2 + 15")
    mt3.metric("OEI configuration", "GEAR UP / MIL", "OPERATING ENGINE")
    st.caption(takeoff.stabilizer_trim_note)
    mc5, mc6, mc7 = st.columns(3)
    mc5.metric("Cruise", f"M{cruise.optimum_mach:.3f} / FL{cruise.optimum_altitude_ft/100:.0f}")
    mc6.metric("Landing", f"15 units / ~{landing.on_speed_ias_est_kt:.0f} kt")
    mc7.metric(
        "Climb profile",
        climb_profile.label,
        f"{climb_profile.time_min:.2f} min / {climb_profile.fuel_burn_lb:,.0f} lb to 10k",
    )
    f1, f2, f3, f4 = st.columns(4)
    f1.metric("Mission burn", f"{fuel.mission_burn_lb:.0f} lb")
    f2.metric("Estimated landing fuel", f"{fuel.landing_fuel_lb:.0f} lb")
    f3.metric("JOKER", f"{fuel.joker_lb:.0f} lb")
    f4.metric("BINGO", f"{fuel.bingo_lb:.0f} lb")
    for warning in fuel.warnings:
        st.warning(warning)
    st.markdown(f"**Climb card: {climb_profile.label}**")
    compact = climb_df[["Altitude ft", "IAS kt", "RPM %", "ROC fpm", "Gradient ft/NM"]]
    st.dataframe(compact, width="stretch", hide_index=True)
    prov_caption(fuel.provenance)

with data_tab:
    st.subheader("Data hierarchy and confidence")
    st.markdown(
        """
1. **Direct legacy performance table point**: highest numerical confidence inside the repository data grid, but v3 does not claim independent NATOPS re-digitization.
2. **Interpolation**: multilinear interpolation inside a tabulated grid.
3. **DCS-calibrated**: anchored to controlled user DCS observations, then scaled by table/physics trends.
4. **Extrapolation**: outside the source grid. Treat conservatively.
5. **Estimated**: physics-based or engineering correction where direct B-model data is not available.

The dedicated F-14B/D performance supplement is not bundled with this project. The UI therefore exposes provenance instead of silently labeling estimates as NATOPS values.
        """
    )
    st.markdown("**Current high-value repository datasets**")
    st.code(
        "data/f14_perf.csv\n"
        "data/f14_landing_natops_full.csv\n"
        "data/f14_cruise_natops.csv\n"
        "data/F110_engine.csv\n"
        "data/dcs_airports.csv"
    )
    st.markdown("**Known legacy data issue**")
    st.write("`data/f14_aero.csv` contains malformed entries and is not used as an authoritative v3 aerodynamic polar.")
    with st.expander("Raw current takeoff result"):
        raw = asdict(takeoff)
        raw["provenance"] = asdict(takeoff.provenance)
        st.json(raw)

st.divider()
st.caption(
    "DCS simulation planning only. This application is not an approved real-world flight-performance source and must not be used for real aircraft operations."
)
