# F-14 EFB

A provenance-aware F-14B electronic flight bag for DCS World.

## Purpose

F-14 EFB is a clean performance architecture built around three rules:

1. Use existing tabulated performance data directly when a valid table exists.
2. Interpolate transparently inside the table and identify extrapolation outside it.
3. When a table does not exist, use calibrated or physics-based estimates and label them explicitly.

This project is for **DCS simulation only**. It is not an approved real-world F-14 performance source and must not be used for real aircraft operations.

## Implemented features

### Takeoff

- DCS airfield/runway database or manual runway input
- TORA / TODA / ASDA
- runway slope
- dry / wet planning correction
- METAR paste or manual weather
- pressure altitude
- wind component calculation
- UP / MANEUVER / FULL / AUTO flap configuration
- automatic reduced-thrust search
- RPM policy floors:
  - UP 85%
  - MANEUVER 90%
  - FULL 96%
- AUTO never selects afterburner
- default 50% headwind credit / 150% tailwind penalty, with a 0% / 150% option
- V1 reference, balanced-field-style V1 sweep, Vr, V2, Vfs, and Vs reference
- integer V-speed presentation
- resolved MILITARY or REDUCED thrust label
- target EIG RPM (N2) and calibrated static fuel-flow reference per engine
- flap-compensated takeoff pitch-trim setting established before the roll, targeting an easy rotation at V2 without excessive backpressure
- separate OEI climb target of V2+15, gear up, with MILITARY thrust on the operating engine
- explicit warning that trim does not command or guarantee climb airspeed
- accelerate-stop distance
- accelerate-go distance
- 10% default runway planning factor
- AEO initial climb gate, default 300 ft/NM
- OEI climb advisory
- explicit provenance/confidence output

### Climb

- named Most Efficient and Minimum Time (MIL) profiles from 1,000 to 10,000 ft
- selectable mission-card climb strategy
- side-by-side modeled time and fuel comparison
- 190–250 KIAS search range
- Most Efficient: lowest 85–100% dry RPM meeting the gradient gate, then best fuel-per-foot speed
- Minimum Time: 100% dry MIL and maximum modeled rate of climb
- climb gradient
- rate of climb
- fuel flow
- drag-index and ISA-deviation sensitivity

### Cruise

- optimum cruise altitude from the legacy weight/drag-index table
- optimum Mach from the table
- estimated TAS
- estimated fuel flow
- estimated specific range
- estimated endurance

### Landing

- direct interpolation of the legacy landing ground-roll grid
- flap DOWN/UP table support
- weight, pressure altitude, temperature, and headwind interpolation
- dry/wet planning
- runway planning factor
- on-speed reference of 15 AOA units
- estimated on-speed IAS
- carrier-weight warning at 54,000 lb when carrier mode is used programmatically

### Energy / maneuvering

- specific excess power
- instantaneous G / turn rate / radius
- sustained G / turn rate / radius
- MIL or AB power
- drag index
- user-selected planning G limit

### Mission card / fuel

- takeoff card
- climb card
- optimum cruise
- landing reference
- phase-based mission fuel estimate
- JOKER / BINGO tracking

## Source hierarchy

The repository contains legacy datasets labeled as NATOPS-derived. Version 3 preserves them, but does **not** automatically assert that those transcriptions are exact or complete. The dedicated F-14B/D performance supplement is not bundled with the repository, so v3 distinguishes:

- DIRECT TABLE
- INTERPOLATED
- EXTRAPOLATED
- CALIBRATED
- ESTIMATED

See `docs/PERFORMANCE_DATA_AUDIT.md` and `docs/MODEL_METHODS.md`.

## Run

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

## Test

```bash
pytest
```

## High-value legacy data retained

- `data/f14_perf.csv`
- `data/f14_landing_natops_full.csv`
- `data/f14_cruise_natops.csv`
- `data/F110_engine.csv`
- `data/f110_ff_to_rpm_knots.csv`
- `data/dcs_airports.csv`

The old `data/f14_aero.csv` is retained for historical traceability but is intentionally not authoritative in v3 because it contains malformed values.
