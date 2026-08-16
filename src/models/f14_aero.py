"""Legacy aerodynamic-model compatibility wrapper for v3."""

from src.f14perf.aero import F14AeroModel


class F14Aero(F14AeroModel):
    pass


AeroModel = F14Aero
