"""Legacy F110 import path retained for v3 compatibility."""

from src.f14perf.engine import F110Deck


class F110EngineModel(F110Deck):
    pass


class F110DeckCompat(F110Deck):
    def thrust_lbf(self, alt_ft=0, mach=0.0, power="MIL"):
        mode = "AB" if str(power).upper() in {"AB", "MAX AB", "AFTERBURNER"} else "MIL"
        return self.point(alt_ft, mach, mode=mode).thrust_lbf_per_engine


F110Deck = F110DeckCompat
