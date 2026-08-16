"""Legacy engine-model compatibility wrapper for v3."""

from src.f14perf.engine import F110Deck


class EngineModel:
    def __init__(self, *_, **__):
        self.deck = F110Deck()

    def compute(self, alt_ft, temp_c, mach, mode="MIL", rpm_pct=100):
        p = self.deck.point(alt_ft, mach, mode=mode, rpm_pct=rpm_pct, oat_c=temp_c)
        return {
            "Engine": "F110-GE-400",
            "Mode": mode.upper(),
            "Thrust": p.thrust_lbf_per_engine,
            "RPM": p.rpm_pct,
            "FuelFlow": p.fuel_flow_pph_per_engine,
        }

    def fuel_flow(self, rpm_pct, oat_c, alt_ft, mach=0.2):
        return self.deck.point(alt_ft, mach, mode="MIL", rpm_pct=rpm_pct, oat_c=oat_c).fuel_flow_pph_per_engine
