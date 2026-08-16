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
- MIL default; reduced dry thrust is isolated as a DCS test mode
- fuel flow is the primary takeoff thrust-set indication
- MIL reference of approximately 10,100 PPH per engine, with 95-104% N2 and 3-10% nozzle as cross-checks
- FF-first reduced-dry input with observation-derived RPM cross-check
- default 0% headwind credit / 150% tailwind penalty, with a 50% / 150% option
- V1 withheld from the operational interface until controlled engine-cut validation exists
- legacy Vr and V2 references plus estimated Vfs and Vs, all visibly guarded
- integer V-speed presentation
- separate FF target and RPM cross-check, using NATOPS MIL indications plus Batumi static and local Henderson +40 C observations
- next-trial takeoff pitch-trim candidates established before the roll: 5.5 ANU UP and 7.0 ANU MANEUVER, targeting an easy rotation without excessive backpressure
- separate OEI climb target of V2+15, gear up, with MILITARY thrust on the operating engine
- explicit note that trim does not command or guarantee climb airspeed
- accelerate-stop distance
- accelerate-go distance
- 15% default runway planning factor
- AEO initial climb gate, default 300 ft/NM
- OEI climb advisory
- direct DCS gross-weight input
- DCS-style station loadout or loadout preset; internal drag units are derived automatically
- validation hold for external-store, hot/high reduced-thrust, and out-of-grid takeoff conditions
- DCS runway-start available distance when known; Henderson 35L defaults to the Tacview-reconciled 4,800 ft instead of the full 6,501 ft
- in-app DCS engine, user-observation, and attached-Tacview motion tables
- explicit provenance/confidence output

### Climb

- NATOPS MIL-climb technique of 6 units AOA at sea level increasing to 9.5 at combat ceiling
- conservative MIL and 95% dry time/fuel integration allowances to the selected cruise trial flight level
- guarded rate-of-climb and time allowances that are not presented as maximum aircraft capability; time and fuel are rounded upward
- conservative two-engine climb fuel burn
- fuel flow displayed in PPH per engine
- weight, stores, and ISA-deviation planning allowances
- the previous low-order climb optimizer was removed after it produced non-credible 18,000 to 27,000 fpm results

### Cruise

- legacy cruise trial altitude and Mach, explicitly marked unverified
- NATOPS optimum-altitude cruise technique of 8 units AOA
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

## Source hierarchy

The repository contains legacy datasets labeled as NATOPS-derived. Version 3 preserves them, but does **not** automatically assert that those transcriptions are exact or complete. The dedicated F-14B/D performance supplement is not bundled with the repository, so v3 distinguishes:

- DIRECT TABLE
- INTERPOLATED
- EXTRAPOLATED
- CALIBRATED
- ESTIMATED

See `docs/PERFORMANCE_DATA_AUDIT.md`, `docs/MODEL_METHODS.md`, `docs/EFB_UX_BENCHMARK_2026-08-16.md`, and `docs/VALIDATION_MATRIX_2026-08-16.md`.

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
