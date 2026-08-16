# V3 Model Methods

## Takeoff

### MIL reference

UP and FULL configurations use the legacy `f14_perf.csv` MIL grid when available.

The independent variables are:

- gross weight
- pressure altitude
- OAT

The outputs are:

- Vs reference
- V1 reference
- Vr
- V2
- ASD
- AGD

### Maneuver flaps

Maneuver flaps use the established 65,000 lb DCS anchor and inherit environmental scaling from the UP table.

### Reduced thrust

The F110 deck supplies MIL and idle endpoints. Reduced dry thrust uses a nonlinear RPM interpolation between those endpoints. Takeoff distance increases with reduced thrust using an empirical acceleration exponent.

This is a calibration model. It is not a claim that engine thrust is a direct algebraic function of indicated RPM in the real aircraft.

### Balanced-field-style V1

The source grid contains a reference V1, ASD, and AGD, but the project does not have a controlled engine-cut sweep for every configuration.

V3 therefore searches candidate V1 in 0.5 kt increments below Vr and minimizes the difference between:

- reject distance, scaled primarily with kinetic energy
- continue distance, adjusted with an explicit estimated OEI sensitivity to engine-failure speed

The UI shows both the table reference V1 and the v3 balanced-field-style V1.

This is intentionally marked ESTIMATED.

### Runway

The default planning factor is 1.10.

V3 separately compares:

- factored ASD to ASDA
- factored AGD to TODA

Wind is applied using ground-speed energy scaling after the takeoff wind policy is applied. The default credits 50% of a headwind and penalizes 150% of a tailwind. A conservative selectable option uses 0% headwind credit while retaining the 150% tailwind penalty. Slope and wet-runway effects are engineering corrections and are labeled accordingly.

### AUTO

Configuration priority:

1. UP
2. MANEUVER
3. FULL

RPM is searched upward from:

- UP 85%
- MANEUVER 90%
- FULL 96%

The first candidate satisfying runway limits and the AEO climb gate is selected.

Afterburner is never selected by AUTO.

## Engine display guidance

The selected dry-thrust setting is displayed as either MILITARY or REDUCED (XX% RPM). The F-14B engine instrument group displays high-pressure compressor RPM (N2) and per-engine fuel flow. The takeoff card therefore shows the selected N2 target and a static per-engine fuel-flow reference interpolated from `f110_ff_to_rpm_knots.csv`.

The fuel-flow knots are controlled DCS observations near sea level. A 100% MIL command uses the highest measured 99% EIG knot instead of extrapolating beyond the calibration. This output is advisory away from the calibration condition.

## Stabilizer trim

The mission-card standard requires a stabilator trim setting established before the takeoff roll and a separate OEI climb reference. The [Heatblur post-start checklist](https://f14.manuals.heatblur.se/f14ab/procedures/post_start.html) specifies trim 000 before takeoff. The same procedure identifies the integrated trim response to flap position and calls for approximately 3 degrees trailing-edge-up stabilizer during the full-flap control check.

F-14 EFB uses an explicit provisional configuration schedule. Recent loaded-aircraft tests show that the current schedule has not yet met the rotation-force acceptance criterion. The EFB currently presents:

- UP takeoff pitch trim: `3.0 ANU`
- MANEUVER takeoff pitch trim: `6.0 ANU`, with `5.0-7.0 ANU` shown only as a trial range
- FULL takeoff pitch trim: `0.0 ANU`
- OEI climb speed: `V2 + 15 KIAS`
- OEI configuration: gear up, MILITARY thrust on the operating engine

The pre-roll settings target an easy rotation at V2 without excessive backpressure. At 62,000 lb with two external tanks and two AIM-9s, the user found 5.0 ANU UP slightly heavy and 6.5 ANU MANEUVER heavy. The next 0.5-ANU test candidates are 5.5 UP and 7.0 MANEUVER, not validated operational values. All settings require a controlled matrix across center-of-gravity and loadout conditions. They are engineering estimates, not a validated NATOPS schedule. Pitch trim does not command an airspeed and cannot guarantee V2+15 after an engine failure. The pilot must control pitch to acquire and maintain the displayed OEI climb speed, then trim as required after establishing the flight path.

## Takeoff stores and validation hold

Takeoff gross weight captures store and fuel weight but does not capture aerodynamic drag. The current takeoff model does not apply the mission drag index or a store-specific drag increment to runway distance or climb. When external stores are selected, the app therefore labels the takeoff result `UNVALIDATED` and suppresses a GO determination. Hot/high reduced-thrust conditions are also held unvalidated because the static RPM-to-fuel-flow reference and reduced-thrust distance correction did not match the Henderson +40 C DCS tests. The app continues to display provisional values to support controlled calibration, but they are not presented as validated runway guidance.

The pilot does not enter a drag index. The Streamlit UI provides loadout presets and a DCS-style station panel for stations 1A, 1B, 2, 3, 4, 5, 6, 7, 8B, and 8A. Gross weight remains a direct DCS input, so the app does not add store weight a second time. The station selections generate low-confidence internal model drag units for climb, cruise, and energy calculations. These units are engineering estimates, not a released F-14 drag-index table, and appear only as supporting model provenance rather than a user input.

The absolute V2 values in the active configuration-specific takeoff model do not use the same baseline as the legacy `vspeeds.csv` table. V3 uses only the legacy Vfs-to-V2 spread and applies it to the active V2:

- `Vfs = active V2 + (legacy Vfs - legacy V2)`

Vfs remains marked ESTIMATED pending controlled DCS validation. It is not used to calculate takeoff trim.

## Initial climb gate

The takeoff decision logic retains the project’s calibrated initial-climb model rather than substituting the general excess-thrust climb model. This keeps the AUTO gate tied to observed DCS behavior.

Default AEO gate: 300 ft/NM.

OEI climb is shown separately as an advisory estimate.

## Climb schedule

From 1,000 to 10,000 ft, the climb model provides two named profiles. Both search 190 to 250 KIAS and retain the 250 KIAS ceiling through 10,000 ft.

### Most Efficient

The optimizer searches upward from 85% dry RPM. At each altitude it selects the lowest RPM that satisfies the requested climb-gradient gate, then chooses the speed with the lowest modeled fuel flow per foot climbed at that power. This preserves the project’s minimum-required-thrust economy policy. It does not assert that the result is the absolute minimum total fuel to altitude.

### Minimum Time (MIL)

The optimizer fixes power at 100% dry MIL and selects the speed with the highest modeled rate of climb at each altitude. Afterburner is not included in this profile.

Each profile reports:

- IAS, TAS, RPM, rate of climb, gradient, and total fuel flow by altitude
- modeled elapsed time to 10,000 ft
- modeled fuel burned to 10,000 ft
- the number of altitude segments that cannot meet the selected gradient gate

The model uses:

- F110 legacy engine deck
- ISA atmosphere with ISA deviation
- low-order clean drag polar

Both schedules and their comparison are ESTIMATED DCS planning products. They are intended for relative strategy selection and are not released F-14B climb charts.

## Landing

Landing ground roll uses direct/interpolated values from `f14_landing_natops_full.csv`.

On-speed AOA is 15 units per current Heatblur cockpit documentation. On-speed IAS is an explicit weight-scaled estimate and is labeled as such.

## Cruise

Optimum altitude and Mach use the legacy cruise table.

The low-order aerodynamic model determines required thrust at the table condition. The F110 deck is then searched for the lowest modeled dry RPM that meets drag. Fuel flow, specific range, and endurance are therefore estimates.

## Energy maneuverability

The energy model calculates:

- specific excess power
- lift-limited instantaneous G
- instantaneous turn rate/radius
- thrust-limited sustained G
- sustained turn rate/radius

The user supplies a planning G limit. V3 does not assert that default as a structural NATOPS limit.

## Fuel

Mission fuel is phase-based:

- taxi/takeoff allowance
- integrated 1,000–10,000 ft climb schedule
- estimated continuation climb to optimum cruise altitude
- cruise fuel from modeled fuel flow and route distance
- descent/approach allowance

The result is a planning estimate, not an F-14 fuel-planning chart replacement.
