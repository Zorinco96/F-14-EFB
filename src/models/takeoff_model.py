"""Legacy takeoff-model compatibility wrapper for v3."""

from src.f14perf.takeoff import AutoTakeoffSelector, TakeoffModel as V3TakeoffModel
from src.f14perf.types import Environment, Runway, TakeoffInputs


class TakeoffModel:
    def __init__(self, *_, **__):
        self.v3 = V3TakeoffModel()
        self.auto = AutoTakeoffSelector()

    def compute_takeoff(
        self,
        weight_lbs=None,
        weight=None,
        runway=None,
        flap_setting="AUTO",
        flap_config=None,
        thrust_mode="AUTO",
        thrust_selection=None,
        weather=None,
        rpm_pct=None,
        thrust_rating=None,
        **_,
    ):
        weight_lb = float(weight_lbs if weight_lbs is not None else weight)
        runway = runway or {}
        weather = weather or {}
        rwy = Runway(
            name="Legacy input",
            heading_deg=float(runway.get("heading_deg", 0)),
            tora_ft=float(runway.get("tora_ft", runway.get("length_ft", 10000))),
            toda_ft=float(runway.get("toda_ft", runway.get("length_ft", 10000))),
            asda_ft=float(runway.get("asda_ft", runway.get("length_ft", 10000))),
            elevation_ft=float(runway.get("elevation_ft", 0)),
            slope_pct=float(runway.get("slope_pct", 0)),
            condition=str(runway.get("condition", "DRY")).upper(),
        )
        env = Environment(
            field_elevation_ft=rwy.elevation_ft or 0,
            oat_c=float(weather.get("oat_C", weather.get("oat_c", 15))),
            qnh_inhg=float(weather.get("pressure_inHg", weather.get("qnh_inhg", 29.92))),
            wind_speed_kt=float(weather.get("wind_kts", 0)),
        )
        flaps = (flap_config or flap_setting or "AUTO").upper()
        thrust = (thrust_selection or thrust_mode or "AUTO").upper()
        explicit_rpm = rpm_pct
        explicit_rating = thrust_rating
        if explicit_rating is None and thrust in {"MIL", "MILITARY"}:
            explicit_rating = "MIL"
        inputs = TakeoffInputs(
            weight_lb=weight_lb,
            environment=env,
            runway=rwy,
            flaps=flaps,
            thrust="MANUAL" if explicit_rating is not None or explicit_rpm is not None else thrust,
            thrust_rating=explicit_rating,
            rpm_pct=explicit_rpm,
        )
        result = self.auto.select(inputs)
        return result.__dict__
