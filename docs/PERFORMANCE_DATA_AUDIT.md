# F-14B Performance Data Audit

## Objective

The v3 project is intended to recover as much F-14B performance behavior as practical from available sources without converting uncertain data into false precision.

The governing source hierarchy is:

1. F-14 NATOPS performance data and limitations
2. Controlled DCS testing analyzed through Tacview
3. A traceable DCS correction to the NATOPS baseline when a difference is material and repeatable
4. Interpolation inside an authoritative table
5. Derived planning assumptions and limited extrapolation

Every calculation should make its position in that hierarchy visible.

## August 2026 operational audit

The following findings changed the application:

1. The previous climb optimizer returned roughly 18,000 to 27,000 fpm in ordinary mission cases. Its low-order polar and legacy engine deck did not support that precision. The optimizer has been removed from the operational path and replaced with a conservative mission-planning schedule.
2. Climb and cruise fuel-flow values passed through `F110Deck.total()` but retained a `per_engine` field name. This made total and per-engine semantics easy to confuse. Operational displays now use explicit PPH per engine fields; mission fuel calculations multiply by two internally.
3. Cruise entries such as 33,900 ft were not immediately usable planning levels. The app rounds them to the nearest 1,000 ft flight level, but now labels the entire altitude/Mach table as an unverified legacy trial because its prior pocket-checklist citation was invalid.
4. The energy section used the same unvalidated low-order polar to publish specific excess power and sustained-turn values. These have been removed. The replacement is limited to ideal coordinated-turn geometry, which does not assert aircraft capability.
5. Landing planning lacked a loadout-sensitive recovery fuel reference. The app now derives launch and recovery zero-fuel weights from one aircraft state, including station-level retained, expended, and jettisoned selections.
6. Repeated low-confidence banners obscured the mission card. The UI now consolidates planning notes in one panel and handles uncertainty through conservative values and an explicit planning hold.
7. The prior 54,000 lb on-speed estimate of 133 KIAS did not match NAVAIR 01-F14AAP-1 Figure 11-8. The flight-test chart gives approximately 140 KIAS with DLC neutral and 131 KIAS with DLC stowed, with a chart tolerance of +/-4 kt. The app now displays both lines.
8. `MEETS PLAN` and later `LEGACY FIT` overstated the confidence of an unverified legacy result. The neutral status is now `REFERENCE ONLY`; external-store, hot/high reduced-thrust, and out-of-grid cases remain on `PLANNING HOLD`.
9. Climb, cruise power, and mission-fuel outputs carried unnecessary precision. Climb time and fuel are rounded upward, cruise power is rounded upward to usable cockpit increments, and mission burn is rounded upward to 500 lb.

These changes do not convert unverified legacy tables into validated data. They reduce false precision and make the remaining assumptions operationally visible.

## September 2026 discrete-rating audit

The follow-on audit made five additional corrections:

1. The continuous takeoff FF slider and one-percent AUTO RPM search were removed. Takeoff accepts only DERATE 3, DERATE 2, DERATE 1, or MIL.
2. The reduced-rating breakpoints are tied to the observed near-SL/ISA EIG knots at 85/90/95% and 3,400/4,800/7,000 PPH per engine. MIL retains the NAVAIR approximately 10,100 PPH/engine indication and 95-to-104-percent N2 range.
3. Reduced-rating FF/RPM guidance is environment-bounded. The Henderson observations support a local DERATE 1 indication, but no general pressure-altitude/temperature law. AUTO retains MIL outside an observation envelope.
4. NAVAIR Figure 14-1 was re-read in page context. It is an airspeed-indicator-failure reference, not a normal best-climb or optimum-cruise performance schedule. The AOA values remain visible only as alternate cues and no longer appear to validate modeled climb or cruise outputs.
5. A maintained scenario battery now covers light, heavy, cold, hot, high, short-runway, tailwind, clean, fleet-defense, strike, external-tank, reduced-rating, MIL, and Henderson Tacview cases. Every case runs through takeoff, climb, cruise, and landing and has an expected safety state.

## September 2026 synchronized-state audit

The loadout and weight audit made six architectural corrections:

1. Independent normal-workflow launch weight, landing weight, starting fuel, and drag entries were removed.
2. `AircraftState` now supplies the same variant, loadout, fuel, weight, and drag state to takeoff, climb, cruise, recovery, and mission-card output.
3. `data/f14_stores.csv` replaces the simplified hard-coded catalog with the Heatblur station matrix, per-station quantities, variant filtering, adapters, fuel capacity, and recovery disposition.
4. Store mass, adapter mass, and drag carry separate source classes. Nominal or unresolved values are not silently promoted.
5. `data/model_authority.csv` names one production model for each major domain. `data/data_inventory.csv` removes competing and obsolete files from the production path without erasing their evidence history.
6. Climb, cruise, landing distance, and mission fuel retain explicit holds where the required NATOPS and controlled Tacview reconciliation remains incomplete.

## Availability constraint

The F-14B flight documentation references a separate performance supplement. That B/D performance volume is not included in this repository, and a complete unrestricted copy has not been established as a reliable public source for this project. As a result, v3 does not claim to recreate every F-14B NATOPS chart directly.

The practical approach is to retain the existing repository grids, audit their internal consistency, compare them with current Heatblur behavior and controlled DCS tests, and only then expand them.

## Current source layers

### 1. Current Heatblur F-14 manual

Primary simulation documentation:

- https://f14.manuals.heatblur.se/

Useful anchors include:

- F-14B total maximum dry thrust listed as 56,400 lbf in the technical specification.
- full flap extension is documented as 35 degrees, with maneuver flap authority lower than full flap.
- 15 units AOA is the on-speed approach reference.
- usable fuel is 16,200 lb internal plus 3,600 lb in two external tanks.
- current F-14B(U) loadout documentation uses 54,000 lb as maximum carrier landing weight.

These values are used as limits/reference context, not as a substitute for missing performance charts.

### 2. Existing repository takeoff grid: `data/f14_perf.csv`

The grid contains F-14B MIL and synthetic AB rows across:

- gross weight: approximately 58,000 / 65,000 / 72,000 lb
- pressure altitude: 0 / 4,000 / 8,000 ft
- OAT: -7 / 15 / 32 / 49 C
- flap table codes: UP=0 and FULL=40 are confirmed in the current file

The 65,000 lb, sea-level, 15 C MIL rows reproduce the DCS calibration anchors already established in the project:

- UP: Vr 159, ASD 2,460 ft, AGD 2,900 ft
- FULL: Vr 140, ASD 2,168 ft, AGD 2,550 ft

The table labels those rows `NATOPS-UP` and `NATOPS-FULL`, but v3 treats that label as legacy provenance rather than independent verification.

AB rows are explicitly marked synthetic in the file. AUTO takeoff therefore does not use AB.

### 3. Maneuver-flap takeoff

A direct maneuver-flap table has not been confirmed in the legacy grid. The current DCS calibration anchor is:

- 65,000 lb
- approximately sea level
- 15 C
- MIL
- Vr approximately 146 kt
- ASD approximately 2,583 ft
- takeoff/accelerate-go distance approximately 2,456 ft

V3 scales this anchor with the UP-table environmental trend and square-root weight speed scaling. This is marked CALIBRATED.

### 4. Legacy Vfs spread: `data/vspeeds.csv`

The legacy V-speed table includes V2 and Vfs versus gross weight, but its absolute V2 baseline does not match the active configuration-specific takeoff grid. V3 does not substitute those absolute values into the takeoff solution. It applies only the table's Vfs-minus-V2 spread to the active V2. Vfs is marked ESTIMATED pending controlled DCS validation and is not used to calculate takeoff trim.

### 5. Pre-roll trim and OEI climb reference

The current Heatblur post-start procedure specifies trim 000 before takeoff and documents approximately 3 degrees trailing-edge-up stabilizer during the full-flap control check. The latest 62,000 lb F-14B(U) tests with two external tanks and two AIM-9s found 5.0 ANU UP slightly heavy and 6.5 ANU MANEUVER heavy. The app now advances one 0.5-ANU test increment to 5.5 UP and 7.0 MANEUVER. These are next controlled-trial candidates, not accepted operational settings. FULL remains at the 0.0 ANU baseline until a controlled test exists. The schedule targets easy rotation through the planned cue without excessive backpressure and requires validation across center-of-gravity and loadout conditions. The OEI climb target is separately defined as V2+15, gear up, with MILITARY thrust on the operating engine. No claim is made that pitch trim automatically commands or holds that airspeed.

### 6. Landing grid: `data/f14_landing_natops_full.csv`

This is a dense ground-roll grid over:

- flap setting
- gross weight
- pressure altitude
- temperature
- headwind

V3 performs multilinear interpolation. Wet-runway corrections are not present in the source grid and are therefore marked ESTIMATED.

Normal on-speed IAS now uses NAVAIR 01-F14AAP-1 Figure 11-8, whose data basis is flight test. At 54,000 lb and 15 units AOA, the digitized references are approximately 140 KIAS with DLC neutral and 131 KIAS with DLC stowed. The chart specifies indicated-airspeed tolerance of +/-4 kt. The chart covers 40,000 through 60,000 lb, 20-degree wing sweep, and all drag indexes.

### 7. Unverified cruise trial table: `data/f14_cruise_natops.csv`

The table contains altitude and Mach values versus gross weight and drag index. Its prior source note cited page 241 of NAVAIR 01-F14AAP-1B. That document is a short pocket checklist and cannot contain the cited page, so the citation was removed during the 2026-08-16 audit.

V3 retains the values only as an unverified DCS trial target, rounds altitude to the nearest 1,000 ft flight level, and recomputes KIAS/TAS at the rounded level. FF per engine, RPM, and specific range are model estimates. NAVAIR Figure 14-1 lists 8 units AOA at optimum cruise altitude only as an alternate cue following an airspeed-indicator failure; it does not validate these altitude or Mach entries.

### 8. F110 deck: `data/F110_engine.csv`

The file contains IDLE, MIL, and AB thrust/fuel-flow points versus altitude and Mach. V3 treats it as a legacy simulation engine deck, not a released certification/NATOPS engine deck.

Reduced dry thrust between idle and MIL is modeled nonlinearly and marked ESTIMATED.

`data/f110_takeoff_ratings.csv` is the operational rating registry. Its three reduced choices must match exact knots in `data/f110_ff_to_rpm_knots.csv`; the loader rejects a mismatch. The rating names are project-standardized DCS selections, not released F110 ratings. The internal nonlinear deck remains only the provisional runway-scaling layer.

### 9. DCS airport database

`data/dcs_airports.csv` provides map, airfield, runway end, heading, TORA/TODA/ASDA, threshold elevation, slope, and notes.

Many rows explicitly contain “verify in DCS” or real-world-data notes. The database is useful operationally, but its notes remain visible because it is not uniformly authoritative for DCS geometry.

### 10. User DCS observation register

`data/dcs_engine_observations.csv` retains the user-confirmed Batumi static engine sweep and the three Henderson +40 C takeoff-power observations. `data/dcs_takeoff_test_log.csv` retains the current Henderson trim/runway tests and one approximate historical Nellis range.

The Nellis 70,000 lb UP/85% row is retained as prior-chat evidence only: approximately 189 KIAS at rotation and approximately 7600-8000 ft to liftoff. Its exact weather, loadout, trim, fuel flow, and measurement method were not preserved, so it is not used as a precise calibration anchor.

The attached Tacviews do not include per-engine fuel flow or RPM. They cannot validate either quantity. Their valid role is event timing, IAS, attitude, flap/throttle ratios, position, and brake-release-to-liftoff motion distance. The correlated Henderson sequence remains an AEO ground-roll check, not an engine calibration or accelerate-go test.

Older Henderson and Mount Pleasant figures that could not be separated from app outputs, stale UI behavior, or expected values are excluded from the observation register. App-calculated distances must never be entered as measured DCS results.

## Known bad legacy data

### `data/f14_aero.csv`

The file contains obvious malformed fields, including examples such as:

- `MANUEVER` misspelling
- an `l_d_max` value of 114.5
- a `cd0` value of 1.021
- FULL sweep values coded as 500

V3 therefore does not use this CSV as the authoritative aerodynamic polar. A low-order estimated polar is isolated in `src/f14perf/aero.py` so it can be replaced cleanly when better data are available.

## NASA research material

NASA NTRS contains multiple F-14 aerodynamic research reports, including low-speed high-lift work and later Dryden aeromodel development. These reports are useful for validating aerodynamic trends and model structure. They do not, by themselves, provide a replacement for the missing B-model operational performance charts.

Relevant NTRS program material includes F-14 high-lift wind-tunnel work and NASA Dryden F-14 aeromodel research. Future v3 work should digitize only figures that are clearly applicable to the F-14B configuration and document every digitized curve separately.

## Interpolation policy

Inside a rectangular table grid, v3 uses multilinear interpolation.

A value is tagged:

- DIRECT_TABLE when all requested axes match a table point
- INTERPOLATED when inside the grid between points
- EXTRAPOLATED when one or more inputs are outside the source axis range
- ESTIMATED when a sparse-grid fallback or physics model is needed

No silent clamping is used to make an out-of-grid result appear tabulated.

## Extrapolation policy

Extrapolation is permitted only when useful for DCS planning and is visibly labeled. It should not be used to establish new calibration truth.

Preferred sequence:

1. interpolate existing tables
2. use nearby DCS calibration
3. use physics trend for direction and curvature
4. cap pathological outputs
5. flag the result

## Highest-priority missing data

1. Controlled engine-failure takeoff sweeps for true balanced-field V1
2. Maneuver-flap takeoff grid across weight/PA/OAT
3. Pre-roll trim, rotation, and OEI V2+15 validation versus weight, CG, and flap configuration
4. AEO and OEI climb gradients versus configuration and RPM
5. Repeated FF/RPM static sweeps across pressure altitude and temperature, with synchronized acceleration or thrust evidence
6. Full climb performance charts through cruise altitude
7. Cruise fuel-flow validation at multiple weights and station loadouts
8. Landing on-speed IAS versus weight in DCS
9. Wet-runway reject and landing tests
10. Accurate station-loadout mapping to aerodynamic drag
11. F-14B(U)-specific differences, if DCS behavior diverges from baseline F-14B

Until items 5 and 6 are calibrated in DCS, climb rates remain conservative planning allowances and cruise RPM/fuel flow remain guarded estimates.

## Interpretation standard

A result that “looks like NATOPS” is not sufficient. The project should retain the numerical source, interpolation coordinates, calibration point, or estimation method needed to reproduce every important output.
