"""Legacy climb-model compatibility wrapper for v3."""

from src.f14perf.climb import ClimbModel as V3ClimbModel


class ClimbModel(V3ClimbModel):
    def climb_gradient(self, weight_lbs, alt_ft, vel_kts, temp=15):
        isa_delta = temp - (15.0 - 1.9812 * alt_ft / 1000.0)
        return self.point(weight_lbs, alt_ft, vel_kts, 100, isa_delta).gradient_ft_nm

    def climb_rate(self, weight_lbs, alt_ft, vel_kts, temp=15):
        isa_delta = temp - (15.0 - 1.9812 * alt_ft / 1000.0)
        return self.point(weight_lbs, alt_ft, vel_kts, 100, isa_delta).roc_fpm

    def climb_profile(self, weight_lbs, alt_ft, vel_kts=250, temp=15, profile="optimum efficiency"):
        speed = {
            "best endurance": 200,
            "best range": 225,
            "optimum efficiency": 250,
            "shortest time": 250,
        }.get(str(profile).lower(), min(250, vel_kts))
        isa_delta = temp - (15.0 - 1.9812 * alt_ft / 1000.0)
        p = self.point(weight_lbs, alt_ft, speed, 100, isa_delta)
        return {
            "profile": profile,
            "speed_kts": p.ias_kt,
            "roc_fpm": p.roc_fpm,
            "gradient_ft_per_nm": p.gradient_ft_nm,
        }
