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
- MIL (100% command) default; reduced-thrust AUTO remains selectable for DCS test planning
- RPM policy floors:
  - UP 85%
  - MANEUVER 90%
  - FULL 96%
- AUTO never selects afterburner
- default 50% headwind credit / 150% tailwind penalty, with a 0% / 150% option
- V1 reference, balanced-field-style V1 sweep, Vr, V2, Vfs, and Vs reference
- integer V-speed presentation
- resolved MILITARY or REDUCED thrust label
- separate commanded RPM and observed EIG RPM/FF references, using Batumi static and local Henderson +40 C observations
- flap-compensated takeoff pitch-trim setting established before the roll, targeting an easy rotation at V2 without excessive backpressure
- separate OEI climb target of V2+15, gear up, with MILITARY thrust on the operating engine
- explicit note that trim does not command or guarantee climb airspeed
- accelerate-stop distance
- accelerate-go distance
- 15% default runway planning factor
- AEO initial climb gate, default 300 ft/NM
- OEI climb advisory
- direct DCS gross-weight input
- DCS-style station loadout or loadout preset; internal drag units are derived automatically
- validation hold for external-store and hot/high reduced-thrust takeoff conditions that are not yet calibrated
- in-app DCS engine and takeoff observation tables
- explicit provenance/confidence output

### Climb

- conservative MIL and 95% dry mission-planning schedules to the selected cruise flight level
- 250 KIAS through 10,000 ft, then 300 KIAS to a Mach 0.72 crossover
- guarded rate-of-climb and time allowances that are not presented as maximum aircraft capability
- conservative two-engine climb fuel burn
- fuel flow displayed in PPH per engine
- weight, stores, and ISA-deviation planning allowances
- the previous low-order climb optimizer was removed after it produced non-credible 18,000 to 27,000 fpm results

### Cruise

- optimum cruise altitude from the legacy weight/drag-index table
- altitude rounded to the nearest usable 1,000 ft flight level
- KIAS and Mach at the rounded flight level
- estimated RPM and fuel flow in PPH per engine
- estimated TAS
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
- 60,000 lb field and 54,000 lb carrier landing references
- maximum landing fuel with all stores retained
- maximum landing fuel with selected expendable stores expended
- conservative expendable-store credits derived from the DCS-style station loadout

### Maneuvering

- ideal coordinated level-turn rate, radius, and time
- KIAS, TAS, and Mach conversion at the selected altitude
- user-selected planning G input
- no Ps, lift-limit, instantaneous-capability, or sustained-turn claim
- the previous low-order energy model is no longer used operationally

### Mission card / fuel

- takeoff card
- climb card
- optimum cruise
- landing reference
- phase-based mission fuel estimate
- JOKER / BINGO tracking
- consolidated mission notes instead of repeated warning banners
- downloadable 768 x 1024 DCS kneeboard PNG

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
