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
- explicit UP / MANEUVER / FULL flap selection
- discrete dry ratings only: DERATE 3, DERATE 2, DERATE 1, and MIL
- AUTO selects the lowest condition-calibrated standardized rating that clears runway and AEO climb gates; MIL is the fail-safe dry setting
- fuel flow is the primary takeoff thrust-set indication
- MIL reference of approximately 10,100 PPH per engine, with 95-104% N2 and 3-10% nozzle as cross-checks
- FF-first discrete reduced ratings tied to the user-confirmed DCS EIG knots; no continuous takeoff FF or RPM slider
- default 0% headwind credit / 150% tailwind penalty, with a 50% / 150% option
- V1 withheld from the operational interface until controlled engine-cut validation exists
- legacy Vr and V2 references plus estimated Vfs and Vs, all visibly guarded
- integer V-speed presentation
- environment-bounded FF/RPM references using NATOPS MIL indications plus Batumi static and local Henderson +40 C observations; unobserved reduced-power atmospheres are held instead of silently corrected
- next-trial takeoff pitch-trim candidates established before the roll: 5.5 ANU UP and 7.0 ANU MANEUVER, targeting an easy rotation without excessive backpressure
- separate OEI climb target of V2+15, gear up, with MILITARY thrust on the operating engine
- explicit note that trim does not command or guarantee climb airspeed
- accelerate-stop distance
- accelerate-go distance
- 15% default runway planning factor
- AEO initial climb gate, default 300 ft/NM
- OEI climb advisory
- direct DCS gross-weight input
- DCS-style station loadout plus Heatblur SCL-based BFM, CAP, strike, TARPS, and fleet-defense presets; internal drag units are derived automatically
- validation hold for external-store, hot/high reduced-thrust, and out-of-grid takeoff conditions
- DCS runway-start available distance when known; Henderson 35L defaults to the Tacview-reconciled 4,800 ft instead of the full 6,501 ft
- in-app DCS engine, user-observation, and attached-Tacview motion tables
- explicit provenance/confidence output

### Climb

- NAVAIR Figure 14-1's 6-to-9.5-unit MIL-climb AOA values are retained only as alternate cues for an airspeed-indicator failure, matching the actual figure context
- conservative MIL and 95% dry time/fuel integration allowances to the selected cruise trial flight level
- guarded rate, time, distance, and fuel allowances that are not presented as NATOPS chart performance; time, distance, and fuel are rounded upward
- conservative two-engine climb fuel burn
- fuel flow displayed in PPH per engine
- weight, stores, and ISA-deviation planning allowances
- the previous low-order climb optimizer was removed after it produced non-credible 18,000 to 27,000 fpm results

### Cruise

- legacy cruise trial altitude and Mach, explicitly marked unverified
- NAVAIR Figure 14-1's 8-unit optimum-altitude AOA is retained only as an alternate cue for an airspeed-indicator failure, not validation of the cruise trial
- altitude rounded to the nearest usable 1,000 ft flight level
- KIAS and Mach at the rounded flight level
- estimated FF planning allowance rounded upward to 250 PPH per engine and RPM cross-check rounded upward to 5%
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
- flight-test-chart on-speed IAS for DLC neutral and DLC stowed, with +/-4 kt chart tolerance
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
- phase-based mission fuel estimate rounded upward to 500 lb
- JOKER / BINGO tracking
- consolidated mission notes instead of repeated warning banners
- downloadable 768 x 1024 DCS kneeboard PNG
- downloadable one-page printable mission-card PDF

### Validation

- maintained light, heavy, cold, hot, high, short-runway, tailwind, fleet-defense, strike, external-tank, reduced-rating, MIL, and Henderson Tacview scenarios
- phase outputs captured for thrust rating, FF, RPM reference, Vr/V2, trim, takeoff distance, climb, cruise, and landing
- CI-safe status expectations that distinguish `REFERENCE ONLY`, `PLANNING HOLD`, and `LIMIT EXCEEDED`
- command-line report: `python tools/run_validation_matrix.py`

## Source hierarchy

The repository contains legacy datasets labeled as NATOPS-derived. Version 3 preserves them, but does **not** automatically assert that those transcriptions are exact or complete. The dedicated F-14B/D performance supplement is not bundled with the repository, so v3 distinguishes:

- DIRECT TABLE
- INTERPOLATED
- EXTRAPOLATED
- CALIBRATED
- ESTIMATED

See `docs/PERFORMANCE_DATA_AUDIT.md`, `docs/MODEL_METHODS.md`, `docs/EFB_UX_BENCHMARK_2026-09-01.md`, and `docs/VALIDATION_MATRIX_2026-09-01.md`.

## Run

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

## Test

```bash
pytest
python tools/run_validation_matrix.py
```

## High-value legacy data retained

- `data/f14_perf.csv`
- `data/f14_landing_natops_full.csv`
- `data/f14_cruise_natops.csv`
- `data/F110_engine.csv`
- `data/f110_ff_to_rpm_knots.csv`
- `data/f110_takeoff_ratings.csv`
- `data/validation_scenarios.csv`
- `data/dcs_airports.csv`

The old `data/f14_aero.csv` is retained for historical traceability but is intentionally not authoritative in v3 because it contains malformed values.
