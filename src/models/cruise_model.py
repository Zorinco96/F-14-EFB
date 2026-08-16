"""Legacy cruise-model compatibility wrapper for v3."""

from src.f14perf.cruise import CruiseModel as V3CruiseModel


class CruiseModel(V3CruiseModel):
    def compute_cruise(self, weight_lbs, altitude_ft=None, profile="Best Range", drag_index=0, **_):
        r = self.optimum(weight_lbs, drag_index)
        return {
            "profile": profile,
            "optimum_altitude_ft": r.optimum_altitude_ft,
            "flight_level": r.flight_level,
            "optimum_mach": r.optimum_mach,
            "optimum_ias_kt": r.optimum_ias_kt,
            "tas_kt": r.tas_kt,
            "rpm_pct": r.rpm_pct,
            "fuel_flow_pph_per_engine": r.fuel_flow_pph_per_engine,
            "specific_range_nm_per_1000lb": r.specific_range_nm_per_1000lb,
        }
