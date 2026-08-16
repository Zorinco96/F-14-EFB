from __future__ import annotations

import math


R = 287.05287
G = 9.80665
GAMMA = 1.4
T0_K = 288.15
P0_PA = 101325.0
RHO0_KG_M3 = 1.225
LAPSE_K_M = 0.0065
KT_PER_MPS = 1.943844492
FT_PER_M = 3.280839895


def pressure_altitude_ft(field_elevation_ft: float, qnh_inhg: float) -> float:
    return float(field_elevation_ft) + (29.92 - float(qnh_inhg)) * 1000.0


def isa_temperature_c(altitude_ft: float) -> float:
    return 15.0 - 1.9812 * (float(altitude_ft) / 1000.0)


def atmosphere(pressure_altitude_ft_value: float, oat_c: float | None = None) -> dict[str, float]:
    h_m = max(-500.0, float(pressure_altitude_ft_value) / FT_PER_M)
    t_isa = T0_K - LAPSE_K_M * h_m
    if h_m <= 11000.0:
        p = P0_PA * (t_isa / T0_K) ** (G / (R * LAPSE_K_M))
    else:
        t11 = T0_K - LAPSE_K_M * 11000.0
        p11 = P0_PA * (t11 / T0_K) ** (G / (R * LAPSE_K_M))
        p = p11 * math.exp(-G * (h_m - 11000.0) / (R * t11))
    t_actual = (isa_temperature_c(pressure_altitude_ft_value) if oat_c is None else float(oat_c)) + 273.15
    rho = p / (R * t_actual)
    sigma = rho / RHO0_KG_M3
    a_mps = math.sqrt(GAMMA * R * t_actual)
    return {
        "temperature_k": t_actual,
        "pressure_pa": p,
        "rho_kg_m3": rho,
        "sigma": sigma,
        "speed_of_sound_kt": a_mps * KT_PER_MPS,
    }


def ias_to_tas_kt(ias_kt: float, sigma: float) -> float:
    return float(ias_kt) / math.sqrt(max(0.05, float(sigma)))


def tas_to_ias_kt(tas_kt: float, sigma: float) -> float:
    return float(tas_kt) * math.sqrt(max(0.05, float(sigma)))


def mach_from_tas(tas_kt: float, speed_of_sound_kt: float) -> float:
    return float(tas_kt) / max(1.0, float(speed_of_sound_kt))


def mach_to_cas_kt(mach: float, pressure_pa: float) -> float:
    """Subsonic calibrated airspeed from Mach and static pressure."""
    m = max(0.0, float(mach))
    pressure = max(1.0, float(pressure_pa))
    impact_pressure = pressure * (
        (1.0 + (GAMMA - 1.0) / 2.0 * m * m) ** (GAMMA / (GAMMA - 1.0)) - 1.0
    )
    sea_level_a_mps = math.sqrt(GAMMA * R * T0_K)
    cas_mps = sea_level_a_mps * math.sqrt(
        2.0
        / (GAMMA - 1.0)
        * ((impact_pressure / P0_PA + 1.0) ** ((GAMMA - 1.0) / GAMMA) - 1.0)
    )
    return cas_mps * KT_PER_MPS


def cas_to_mach(cas_kt: float, pressure_pa: float) -> float:
    """Subsonic Mach from calibrated airspeed and static pressure."""
    sea_level_a_mps = math.sqrt(GAMMA * R * T0_K)
    cas_mps = max(0.0, float(cas_kt)) / KT_PER_MPS
    impact_pressure = P0_PA * (
        (1.0 + (GAMMA - 1.0) / 2.0 * (cas_mps / sea_level_a_mps) ** 2)
        ** (GAMMA / (GAMMA - 1.0))
        - 1.0
    )
    pressure = max(1.0, float(pressure_pa))
    return math.sqrt(
        2.0
        / (GAMMA - 1.0)
        * ((impact_pressure / pressure + 1.0) ** ((GAMMA - 1.0) / GAMMA) - 1.0)
    )


def cas_to_tas_kt(cas_kt: float, pressure_pa: float, speed_of_sound_kt: float) -> float:
    return cas_to_mach(cas_kt, pressure_pa) * float(speed_of_sound_kt)
