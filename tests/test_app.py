from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _element(elements, label):
    return next(element for element in elements if element.label == label)


def test_default_interface_uses_one_calculated_aircraft_state():
    app = AppTest.from_file(APP_PATH, default_timeout=40).run()

    assert not app.exception
    assert _element(app.metric, "Departure").value in {"REFERENCE ONLY", "PLANNING HOLD", "LIMIT EXCEEDED"}
    assert _element(app.metric, "SET FF / engine").value.endswith("PPH")
    assert _element(app.metric, "Launch gross weight").value == "58,420 lb"
    assert _element(app.metric, "V1").value == "WITHHELD"
    assert len(app.get("download_button")) == 2
    assert all(item.label != "Takeoff gross weight (lb)" for item in app.number_input)
    assert all(item.label != "Planned landing gross weight (lb)" for item in app.number_input)
    assert len(app.dataframe) == 0


def test_loadout_and_fuel_changes_propagate_to_launch_weight():
    app = AppTest.from_file(APP_PATH, default_timeout=40).run()
    _element(app.selectbox, "Preset").set_value("2 external tanks + 2 AIM-9")
    app.run()

    assert not app.exception
    assert _element(app.number_input, "External fuel (lb)").value == 3_600
    assert _element(app.metric, "Launch gross weight").value == "63,600 lb"

    _element(app.number_input, "External fuel (lb)").set_value(0.0)
    app.run()
    assert _element(app.metric, "Launch gross weight").value == "60,000 lb"


def test_recovery_disposition_changes_recovery_weight_without_rebuilding_loadout():
    app = AppTest.from_file(APP_PATH, default_timeout=40).run()
    _element(app.selectbox, "Preset").set_value("2 external tanks + 2 AIM-9")
    app.run()
    retained_weight = _element(app.metric, "Expected recovery weight").value

    _element(app.selectbox, "Recovery plan - STA 2").set_value("JETTISON")
    app.run()
    jettison_weight = _element(app.metric, "Expected recovery weight").value

    assert not app.exception
    assert retained_weight != jettison_weight


def test_custom_selector_exposes_bu_store_inventory_by_station():
    app = AppTest.from_file(APP_PATH, default_timeout=40).run()
    _element(app.selectbox, "Preset").set_value("Custom station loadout")
    app.run()
    station_3 = _element(app.selectbox, "STA 3")
    assert any("GBU-31(V)2/B" in option for option in station_3.options)
    assert any("AIM-54A Mk 60" in option for option in station_3.options)
    assert _element(app.selectbox, "STA 2").options == [
        "Empty station",
        "FPU-1 external fuel tank | TANK PYLON",
    ]


def test_engineering_detail_is_progressively_disclosed():
    app = AppTest.from_file(APP_PATH, default_timeout=40).run()
    assert len(app.dataframe) == 0
    _element(app.checkbox, "Engineering / data-audit mode").set_value(True)
    app.run()
    assert not app.exception
    assert len(app.dataframe) >= 2
