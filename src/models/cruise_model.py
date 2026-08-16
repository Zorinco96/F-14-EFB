"""Legacy cruise-model compatibility wrapper for v3."""

from src.f14perf.cruise import CruiseModel as V3CruiseModel


class CruiseModel(V3CruiseModel):
    def compute_cruise(self, weight_lbs, altitude_ft=None, profile="Best Range", drag_index=0, **_):
        r = self.optimum(weight_lbs, drag_index)
        return {
            "profile": profile,
            "optimum_altitude_ft": r.optimum_altitude_ft,
            "optimum_mach": r.optimum_mach,
            "tas_kt": r.tas_kt,
            "fuel_flow_pph": r.fuel_flow_pph_total,
            "specific_range_nm_per_1000lb": r.specific_range_nm_per_1000lb,
        }
