from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _element(elements, label):
    return next(element for element in elements if element.label == label)


def test_default_interface_uses_neutral_status_and_coarse_planning_outputs():
    app = AppTest.from_file(APP_PATH, default_timeout=30).run()

    assert not app.exception
    assert _element(app.metric, "Departure").value == "LEGACY FIT"
    assert _element(app.metric, "V2 / trial trim").value.endswith("5.5 ANU")
    assert _element(app.metric, "Time allowance").value.endswith("min")
    assert _element(app.metric, "Fuel allowance").value.endswith("lb")
    assert _element(app.metric, "Normal DLC neutral").value == "~140 KIAS"
    assert len(app.get("download_button")) == 1


def test_henderson_observation_is_shown_without_a_go_call():
    app = AppTest.from_file(APP_PATH, default_timeout=30).run()
    _element(app.selectbox, "Preset").set_value("2 external tanks + 2 AIM-9")
    _element(app.selectbox, "DCS map").set_value("Nevada")
    app.run()
    _element(app.selectbox, "Airfield").set_value("Henderson Executive")
    app.run()
    _element(app.selectbox, "Runway").set_value("35L")
    _element(app.selectbox, "Takeoff flaps").set_value("MANEUVER")
    _element(app.number_input, "Takeoff gross weight (lb)").set_value(62_000)
    _element(app.number_input, "OAT (°C)").set_value(40.0)
    _element(app.slider, "Takeoff RPM (%)").set_value(95)
    app.run()

    assert not app.exception
    assert _element(app.metric, "Departure").value == "PLANNING HOLD"
    assert _element(app.metric, "V2 / trial trim").value.endswith("7.0 ANU")
    assert _element(app.metric, "Liftoff distance").value == "6,101 ft"
    assert _element(app.metric, "Test trim / force").value == "6.5 ANU"
    assert any("+1,654 ft" in caption.value for caption in app.caption)
