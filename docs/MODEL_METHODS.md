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

The default planning factor is 1.15.

V3 separately compares:

- factored ASD to ASDA
- factored AGD to TODA

Wind is applied using ground-speed energy scaling after the takeoff wind policy is applied. The default credits 0% of a headwind and penalizes 150% of a tailwind. A selectable option credits 50% headwind while retaining the 150% tailwind penalty. Slope and wet-runway effects are engineering corrections and are labeled accordingly.

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

The selected dry-thrust command is displayed as either MILITARY or REDUCED (XX% RPM). The F-14B engine instrument group displays high-pressure compressor RPM (N2) and per-engine fuel flow. The takeoff card separates commanded RPM from the observed EIG reference. For MIL, a 100% model command is paired with the user-observed approximately 99% EIG RPM and 10,000 pph per engine rather than pretending the cockpit indication was exactly 100%.

`f110_ff_to_rpm_knots.csv` contains the user-confirmed Batumi standard-day static sweep: 71/80/85/90/95/99% RPM at approximately 1200/2500/3400/4800/7000/10000 pph per engine. A 100% MIL command uses the highest measured 99% EIG knot instead of extrapolating beyond the calibration.

`f110_takeoff_ff_environment.csv` adds the Henderson +40 C observations. Near the tested condition and only from 95 through 98% RPM, the app uses 5250 pph at 95% (the mean of 5000 and 5500) and 6000 pph at 98%. This is a local interpolation from three observations, not a general altitude/temperature fuel-flow law. Outside that narrow envelope, the app retains the Batumi static reference and labels it advisory.

## Stabilizer trim

The mission-card standard requires a stabilator trim setting established before the takeoff roll and a separate OEI climb reference. The [Heatblur post-start checklist](https://f14.manuals.heatblur.se/f14ab/procedures/post_start.html) specifies trim 000 before takeoff. The same procedure identifies the integrated trim response to flap position and calls for approximately 3 degrees trailing-edge-up stabilizer during the full-flap control check.

F-14 EFB uses an explicit provisional configuration schedule. Recent loaded-aircraft tests show that the previous schedule did not meet the rotation-force acceptance criterion. The EFB now presents the next controlled DCS trial candidates:

- UP takeoff pitch trim: `5.5 ANU`, after the `5.0 ANU` test was slightly heavy
- MANEUVER takeoff pitch trim: `7.0 ANU`, after the `6.5 ANU` test was heavy
- FULL takeoff pitch trim: `0.0 ANU`
- OEI climb speed: `V2 + 15 KIAS`
- OEI configuration: gear up, MILITARY thrust on the operating engine

The pre-roll settings target an easy rotation through the planned cue without excessive backpressure. They are not validated operational values. All settings require a controlled matrix across center-of-gravity and loadout conditions. They are engineering estimates, not a validated NATOPS schedule. Pitch trim does not command an airspeed and cannot guarantee V2+15 after an engine failure. The pilot must control pitch to acquire and maintain the displayed OEI climb speed, then trim as required after establishing the flight path.

## Takeoff stores and validation hold

Takeoff gross weight captures store and fuel weight but does not capture aerodynamic drag. The current takeoff model does not apply the mission drag index or a store-specific drag increment to runway distance or climb. When external stores are selected, the app therefore labels the takeoff result `UNVALIDATED` and suppresses a GO determination. Hot/high reduced-thrust conditions are also held unvalidated. The Henderson fuel-flow observations are now used locally, but the thrust and runway-distance correction still does not reproduce the +40 C takeoff tests. The app continues to display provisional values to support controlled calibration, but they are not presented as validated runway guidance.

The corrected 62,000 lb MANEUVER run records rotation at 143 KIAS and 5401 ft, followed by liftoff at 6101 ft. This is a 700 ft rotation segment. It is an all-engines-operating liftoff observation and must not be mislabeled as accelerate-go or 50-ft distance.

The pilot does not enter a drag index. The Streamlit UI provides loadout presets and a DCS-style station panel for stations 1A, 1B, 2, 3, 4, 5, 6, 7, 8B, and 8A. Gross weight remains a direct DCS input, so the app does not add store weight a second time. The station selections generate low-confidence internal model drag units for climb, cruise, and energy calculations. These units are engineering estimates, not a released F-14 drag-index table, and appear only as supporting model provenance rather than a user input.

The absolute V2 values in the active configuration-specific takeoff model do not use the same baseline as the legacy `vspeeds.csv` table. V3 uses only the legacy Vfs-to-V2 spread and applies it to the active V2:

- `Vfs = active V2 + (legacy Vfs - legacy V2)`

Vfs remains marked ESTIMATED pending controlled DCS validation. It is not used to calculate takeoff trim.

## Initial climb gate

The takeoff decision logic retains the project’s calibrated initial-climb model rather than substituting the general excess-thrust climb model. This keeps the AUTO gate tied to observed DCS behavior.

Default AEO gate: 300 ft/NM.

OEI climb is shown separately as an advisory estimate.

## Climb schedule

The August 2026 audit found that the previous excess-thrust optimizer produced approximately 18,000 to 27,000 fpm in common mission conditions and only a few hundred pounds of climb fuel. Those outputs were not credible and are no longer used operationally.

The revised model provides two guarded planning schedules to the rounded optimum cruise flight level:

- MIL climb planning at 100% dry RPM
- conservative dry planning at 95% RPM

Both use 250 KIAS through 10,000 ft, then 300 KIAS to a Mach 0.72 crossover. Rate of climb is a deliberately conservative planning allowance adjusted for gross weight, positive ISA deviation, and the selected store-drag allowance. It is not a prediction of maximum climb capability. Operational output rounds elapsed time up to a whole minute and fuel up to 500 lb.

Each profile reports:

- IAS, TAS, RPM, planning rate of climb, gradient, and fuel flow per engine by altitude
- guarded elapsed time to cruise altitude
- conservative two-engine fuel burned to cruise altitude
- the number of altitude segments that cannot meet the selected gradient gate

The legacy F110 deck supplies only the per-engine fuel-flow estimate. The low-order F-14 aerodynamic polar is no longer used to predict operational climb rate. Both schedules are ESTIMATED DCS planning products and are biased toward time and fuel margin.

## Landing

Landing ground roll uses direct/interpolated values from `f14_landing_natops_full.csv`.

On-speed AOA is 15 units. On-speed IAS uses the flight-test curves in NAVAIR 01-F14AAP-1 Figure 11-8 for 20-degree wing sweep and all drag indexes. The app displays both normal DLC-neutral IAS and DLC-stowed IAS with the chart's +/-4 kt tolerance.

Landing fuel quick-reference calculations use:

- 60,000 lb maximum field landing gross weight
- 54,000 lb maximum carrier/FCLP landing gross weight
- entered takeoff gross weight minus starting fuel as retained zero-fuel weight
- selected expendable-store credits rounded down from nominal store weights
- roughly 20,000 lb maximum usable fuel

Maximum fuel values are rounded down to the nearest 100 lb. Tanks, pods, racks, adapters, and unclassified stores remain in retained weight.

## Cruise

Optimum altitude and Mach use the legacy cruise table. Raw altitude is rounded to the nearest 1,000 ft usable flight level before the display condition is calculated.

The low-order aerodynamic model determines required thrust at the rounded flight level. The F110 deck is then searched for the lowest modeled dry RPM that meets drag. Because that one-percent equilibrium result is not a cockpit calibration, the app rounds the initial RPM upward to 5-percent increments, recomputes fuel flow at that setting, and rounds fuel flow upward to 250 PPH per engine. Specific range and endurance use the two-engine aircraft total internally and remain estimates.

## Maneuver geometry

The audit found that specific excess power and sustained-turn outputs depended on the unvalidated low-order F-14 polar and therefore carried more precision than the source data supported. Those outputs were removed from the operational interface.

The revised maneuver section calculates only ideal coordinated level-turn geometry from selected KIAS, altitude, and planning G:

- TAS and Mach
- turn rate
- turn radius
- 180-degree and 360-degree turn time

The user supplies planning G. The model does not assert that the selected G is aerodynamically available, sustainable, or structurally permitted.

## Fuel

Mission fuel is phase-based:

- taxi/takeoff allowance
- integrated conservative climb schedule to the rounded cruise flight level
- cruise fuel from modeled fuel flow and route distance
- descent/approach allowance

The result is a planning estimate, not an F-14 fuel-planning chart replacement. Total mission burn is rounded upward to 500 lb.
