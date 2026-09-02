import pytest

from src.models.derate import DerateCalculator


def _conditions():
    return {
        "weight_lbs": 65_000,
        "runway": {"length_ft": 8_000, "elevation_ft": 0},
        "weather": {"oat_c": 15, "qnh_inhg": 29.92},
        "flap_setting": "UP",
    }


def test_legacy_derate_facade_accepts_only_exact_discrete_knot():
    card = DerateCalculator("F-14B", "F110").compute_manual_derate(90, _conditions())
    assert card["Thrust Rating"] == "DERATE 2"
    assert card["Fuel Flow (pph/engine)"] == 4_800


def test_legacy_derate_facade_rejects_continuous_rpm_and_never_escalates_to_ab():
    calculator = DerateCalculator("F-14B", "F110")
    with pytest.raises(ValueError, match="Continuously variable takeoff RPM is disabled"):
        calculator.compute_manual_derate(92, _conditions())
    card = calculator.compute_auto_derate(_conditions())
    assert card["Thrust Rating"] in {"DERATE 3", "DERATE 2", "DERATE 1", "MIL"}
    assert "AFTERBURNER" not in str(card)
