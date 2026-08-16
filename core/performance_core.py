"""Compatibility facade for F-14 EFB.

Legacy code imported helpers from core.performance_core. The previous file was
malformed and contained placeholders. New work should import src.f14perf
modules directly.
"""

from src.f14perf.atmosphere import atmosphere, pressure_altitude_ft
from src.f14perf.aero import F14AeroModel
from src.f14perf.climb import ClimbModel
from src.f14perf.cruise import CruiseModel
from src.f14perf.landing import LandingModel
from src.f14perf.takeoff import AutoTakeoffSelector, TakeoffModel

__all__ = [
    "atmosphere",
    "pressure_altitude_ft",
    "F14AeroModel",
    "ClimbModel",
    "CruiseModel",
    "LandingModel",
    "TakeoffModel",
    "AutoTakeoffSelector",
]
