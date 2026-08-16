from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .provenance import Provenance


@dataclass(frozen=True)
class Environment:
    field_elevation_ft: float = 0.0
    oat_c: float = 15.0
    qnh_inhg: float = 29.92
    wind_dir_deg: Optional[float] = None
    wind_speed_kt: float = 0.0
    wind_gust_kt: Optional[float] = None


@dataclass(frozen=True)
class Runway:
    name: str = "Manual"
    heading_deg: float = 0.0
    tora_ft: float = 8000.0
    toda_ft: float = 8000.0
    asda_ft: float = 8000.0
    slope_pct: float = 0.0
    condition: str = "DRY"
    elevation_ft: Optional[float] = None
    notes: str = ""


@dataclass(frozen=True)
class TakeoffInputs:
    weight_lb: float
    environment: Environment
    runway: Runway
    flaps: str = "AUTO"
    thrust: str = "AUTO"
    rpm_pct: Optional[float] = None
    runway_factor: float = 1.10
    climb_target_ft_nm: float = 300.0
    headwind_credit_pct: float = 50.0
    tailwind_penalty_pct: float = 150.0


@dataclass
class TakeoffResult:
    feasible: bool
    flaps: str
    rpm_pct: float
    v1_kt: float
    v1_reference_kt: float
    vr_kt: float
    v2_kt: float
    vfs_kt: float
    vs_kt: float
    asd_ft: float
    agd_ft: float
    factored_asd_ft: float
    factored_agd_ft: float
    asda_margin_ft: float
    toda_margin_ft: float
    climb_gradient_ft_nm: float
    climb_gradient_oei_ft_nm: float
    pressure_altitude_ft: float
    headwind_kt: float
    provenance: Provenance
    credited_headwind_kt: float = 0.0
    thrust_setting: str = "MILITARY"
    fuel_flow_pph_per_engine: float = 0.0
    fuel_flow_pph_total: float = 0.0
    stabilizer_trim_anu: Optional[float] = None
    oei_climb_speed_kt: Optional[float] = None
    stabilizer_trim_note: str = "Takeoff pitch-trim setting is not modeled."
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class ClimbPoint:
    altitude_ft: float
    ias_kt: float
    tas_kt: float
    rpm_pct: float
    roc_fpm: float
    gradient_ft_nm: float
    fuel_flow_pph_total: float
    provenance: Provenance


@dataclass
class ClimbProfile:
    strategy: str
    label: str
    points: list[ClimbPoint]
    time_min: float
    fuel_burn_lb: float
    altitude_gain_ft: float
    target_gradient_ft_nm: float
    unmet_segments: int
    provenance: Provenance
    notes: list[str] = field(default_factory=list)


@dataclass
class LandingResult:
    ground_roll_ft: float
    factored_distance_ft: float
    on_speed_aoa_units: float
    on_speed_ias_est_kt: float
    runway_margin_ft: float
    provenance: Provenance
    warnings: list[str] = field(default_factory=list)


@dataclass
class CruiseResult:
    optimum_altitude_ft: float
    optimum_mach: float
    tas_kt: float
    fuel_flow_pph_total: float
    specific_range_nm_per_1000lb: float
    endurance_hr_per_1000lb: float
    provenance: Provenance
    notes: list[str] = field(default_factory=list)


@dataclass
class EnergyResult:
    speed_ias_kt: float
    mach: float
    ps_fps: float
    instantaneous_g: float
    instantaneous_turn_rate_dps: float
    instantaneous_radius_ft: float
    sustained_g: float
    sustained_turn_rate_dps: float
    sustained_radius_ft: float
    provenance: Provenance


@dataclass
class FuelPlan:
    starting_fuel_lb: float
    taxi_takeoff_lb: float
    climb_lb: float
    cruise_lb: float
    descent_approach_lb: float
    mission_burn_lb: float
    landing_fuel_lb: float
    joker_lb: float
    bingo_lb: float
    provenance: Provenance
    warnings: list[str] = field(default_factory=list)


@dataclass
class MissionCard:
    takeoff: TakeoffResult
    climb: list[ClimbPoint]
    cruise: CruiseResult
    landing: LandingResult
    fuel: FuelPlan
    metadata: dict[str, Any] = field(default_factory=dict)
