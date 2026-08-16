# F-14B Performance Data Audit

## Objective

The v3 project is intended to recover as much F-14B performance behavior as practical from available sources without converting uncertain data into false precision.

The desired hierarchy is:

1. Direct table point
2. Interpolation inside a credible table
3. DCS-calibrated model
4. Limited extrapolation
5. Physics-based estimate

Every calculation should make its position in that hierarchy visible.

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
- usable fuel is roughly 20,000 lb.
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

The current Heatblur post-start procedure specifies trim 000 before takeoff and documents approximately 3 degrees trailing-edge-up stabilizer during the full-flap control check. F-14 EFB retains provisional app values of 6.0 ANU MANEUVER, 3.0 ANU UP, and 0.0 ANU FULL while controlled testing continues. The displayed 5.0 to 7.0 ANU MANEUVER range is a trial range, not an accepted band. In the latest 62,000 lb F-14B(U) test with two external tanks and two AIM-9s, 5.0 ANU UP was slightly heavy and 6.5 ANU MANEUVER was heavy. The next 0.5-ANU candidates are 5.5 UP and 7.0 MANEUVER. The schedule targets easy rotation at V2 without excessive backpressure and requires validation across center-of-gravity and loadout conditions. The OEI climb target is separately defined as V2+15, gear up, with MILITARY thrust on the operating engine. No claim is made that pitch trim automatically commands or holds that airspeed.

### 6. Landing grid: `data/f14_landing_natops_full.csv`

This is a dense ground-roll grid over:

- flap setting
- gross weight
- pressure altitude
- temperature
- headwind

V3 performs multilinear interpolation. Wet-runway corrections are not present in the source grid and are therefore marked ESTIMATED.

### 7. Cruise table: `data/f14_cruise_natops.csv`

The table provides optimum altitude and optimum Mach versus gross weight and drag index. The source note identifies a previously digitized F-14 performance table.

V3 uses the table directly for optimum altitude/Mach. Fuel flow and specific range are then estimated with the F110 and aerodynamic models.

### 8. F110 deck: `data/F110_engine.csv`

The file contains IDLE, MIL, and AB thrust/fuel-flow points versus altitude and Mach. V3 treats it as a legacy simulation engine deck, not a released certification/NATOPS engine deck.

Reduced dry thrust between idle and MIL is modeled nonlinearly and marked ESTIMATED.

### 9. DCS airport database

`data/dcs_airports.csv` provides map, airfield, runway end, heading, TORA/TODA/ASDA, threshold elevation, slope, and notes.

Many rows explicitly contain “verify in DCS” or real-world-data notes. The database is useful operationally, but its notes remain visible because it is not uniformly authoritative for DCS geometry.

### 10. User DCS observation register

`data/dcs_engine_observations.csv` retains the user-confirmed Batumi static engine sweep and the three Henderson +40 C takeoff-power observations. `data/dcs_takeoff_test_log.csv` retains the current Henderson trim/runway tests and one approximate historical Nellis range.

The Nellis 70,000 lb UP/85% row is retained as prior-chat evidence only: approximately 189 KIAS at rotation and approximately 7600-8000 ft to liftoff. Its exact weather, loadout, trim, fuel flow, and measurement method were not preserved, so it is not used as a precise calibration anchor.

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
5. Full climb performance charts through cruise altitude
6. Cruise fuel-flow validation at multiple weights and station loadouts
7. Landing on-speed IAS versus weight in DCS
8. Wet-runway reject and landing tests
9. Accurate station-loadout mapping to aerodynamic drag
10. F-14B(U)-specific differences, if DCS behavior diverges from baseline F-14B

## Interpretation standard

A result that “looks like NATOPS” is not sufficient. The project should retain the numerical source, interpolation coordinates, calibration point, or estimation method needed to reproduce every important output.
