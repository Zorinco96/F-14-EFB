from src.f14perf.validation import run_validation_battery


def test_maintained_validation_battery_matches_expected_safety_states():
    outcomes = run_validation_battery()
    assert len(outcomes) >= 10
    assert outcomes["status_match"].all(), outcomes[
        ["case_id", "expected_status", "actual_status"]
    ].to_dict("records")


def test_operational_battery_covers_requested_environment_and_loadout_axes():
    outcomes = run_validation_battery()
    ids = set(outcomes["case_id"])
    assert {
        "LIGHT_COLD_LONG",
        "HOT_HIGH_HEAVY",
        "SHORT_RUNWAY",
        "FLEET_DEFENSE",
        "STRIKE",
        "EXTERNAL_TANKS",
        "HENDERSON_TACVIEW",
    } <= ids
    assert (outcomes["climb_distance_nm"] > 0).all()
    assert (outcomes["climb_fuel_lb"] > 0).all()
    assert (outcomes["cruise_ff_pph_per_engine"] > 0).all()
    assert (outcomes["landing_ground_roll_ft"] > 0).all()


def test_hot_high_and_tailwind_trends_are_conservative():
    outcomes = run_validation_battery().set_index("case_id")
    assert outcomes.loc["HOT_HIGH_HEAVY", "takeoff_distance_ft"] > outcomes.loc["HOT_SEA_LEVEL", "takeoff_distance_ft"]
    assert outcomes.loc["TAILWIND", "takeoff_distance_ft"] > outcomes.loc["ISA_MIL", "takeoff_distance_ft"]


def test_henderson_tacview_anchor_remains_close_and_held():
    outcome = run_validation_battery().set_index("case_id").loc["HENDERSON_TACVIEW"]
    assert abs(outcome["takeoff_distance_ft"] / 1.15 - 4_853) / 4_853 < 0.10
    assert outcome["actual_status"] == "PLANNING_HOLD"
