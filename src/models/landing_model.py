"""Legacy landing-model compatibility wrapper for v3."""

from src.f14perf.landing import LandingModel as V3LandingModel
from src.f14perf.types import Environment, Runway


class LandingModel(V3LandingModel):
    def compute_landing(self, weight_lbs, flap_setting="FULL", runway_condition="DRY", **_):
        env = Environment(field_elevation_ft=0, oat_c=15, qnh_inhg=29.92)
        rwy = Runway(
            name="Legacy input",
            heading_deg=0,
            tora_ft=10000,
            toda_ft=10000,
            asda_ft=10000,
            elevation_ft=0,
            condition=runway_condition.upper(),
        )
        flap = "DOWN" if flap_setting.upper() in {"FULL", "DOWN"} else "UP"
        r = self.calculate(weight_lbs, env, rwy, flap)
        return r.__dict__
