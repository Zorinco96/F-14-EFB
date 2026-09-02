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

### Discrete dry ratings

The operational takeoff interface no longer accepts a continuously variable FF or RPM. `data/f110_takeoff_ratings.csv` defines four fixed choices in increasing thrust order:

| Rating | Nominal model knot | Near-SL/ISA FF per engine | Evidence |
| --- | ---: | ---: | --- |
| DERATE 3 | 85% | 3,400 PPH | User-confirmed Batumi static DCS EIG observation |
| DERATE 2 | 90% | 4,800 PPH | User-confirmed Batumi static DCS EIG observation |
| DERATE 1 | 95% | 7,000 PPH | Batumi static observation plus limited Henderson 95% evidence |
| MIL | MIL detent | approximately 10,100 PPH | NAVAIR 01-F14AAP-1 normal on-deck indication |

The names describe standardized selections, not certified F110 thrust ratings. The legacy F110 deck still supplies a nonlinear thrust ratio internally to scale the provisional runway model, but arbitrary takeoff RPM values are rejected. That internal correction is ESTIMATED and does not establish that indicated RPM is a direct measure of delivered thrust.

Near the Henderson +40 C observation point, DERATE 1 uses the local 5,250 PPH/engine aggregate at approximately 95% N2. The lower ratings have no local observation and are not condition-calibrated there. Away from the Batumi or Henderson observation envelopes, AUTO retains MIL rather than inventing an atmospheric FF correction.

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

AUTO searches only the discrete choices permitted for each configuration:

- UP: DERATE 3, DERATE 2, DERATE 1, MIL
- MANEUVER: DERATE 2, DERATE 1, MIL
- FULL: MIL

The first condition-calibrated candidate satisfying runway limits and the AEO climb gate is selected. If no calibrated candidate clears the gates, AUTO retains the best MIL result as the fail-safe dry setting and reports the limiting state.

Afterburner is never selected by AUTO.

## Engine display guidance

Fuel flow per engine is the primary takeoff setpoint. RPM is a secondary cross-check. This is a cockpit-workload decision supported by the discrete FF targets and by the observed environmental variation in the FF/RPM relationship. It is not a claim that fuel flow alone proves actual thrust.

The F-14B engine instrument group displays high-pressure compressor RPM (N2) and per-engine fuel flow. For MIL, the app uses the NAVAIR normal on-deck indication of approximately 10,100 PPH per engine and a 95-to-104-percent N2 cross-check. For reduced ratings, the card shows the observed FF target for the applicable environment and an approximate RPM cross-check. It never implies that one RPM value represents identical thrust in all atmospheres.

`f110_ff_to_rpm_knots.csv` contains the user-confirmed Batumi standard-day static sweep: 71/80/85/90/95/99% RPM at approximately 1200/2500/3400/4800/7000/10000 pph per engine. A 100% MIL command uses the highest measured 99% EIG knot instead of extrapolating beyond the calibration.

`f110_takeoff_ff_environment.csv` adds the Henderson +40 C observations. Near the tested condition and only from 95 through 98% RPM, the underlying evidence layer retains 5,250 PPH at 95% (the mean of 5,000 and 5,500) and 6,000 PPH at 98%. Only the 95% point corresponds to a standardized rating. This is local indication evidence, not a general altitude/temperature fuel-flow or thrust law.

## Stabilizer trim

The mission-card standard requires a stabilator trim setting established before the takeoff roll and a separate OEI climb reference. The [Heatblur post-start checklist](https://f14.manuals.heatblur.se/f14ab/procedures/post_start.html) specifies trim 000 before takeoff. The same procedure identifies the integrated trim response to flap position and calls for approximately 3 degrees trailing-edge-up stabilizer during the full-flap control check.

F-14 EFB uses an explicit provisional configuration schedule. Recent loaded-aircraft tests show that the previous schedule did not meet the rotation-force acceptance criterion. The EFB now presents the next controlled DCS trial candidates:

- UP takeoff pitch trim: `5.5 ANU`, after the `5.0 ANU` test was slightly heavy
- MANEUVER takeoff pitch trim: `7.0 ANU`, after the `6.5 ANU` test was heavy
- FULL takeoff pitch trim: `0.0 ANU`
- OEI climb speed: `V2 + 15 KIAS`
- OEI configuration: gear up, MILITARY thrust on the operating engine

The pre-roll settings target an easy rotation through the planned cue without excessive backpressure. They are not validated operational values. All settings require a controlled matrix across center-of-gravity and loadout conditions. They are engineering estimates, not a validated NATOPS schedule. Pitch trim does not command an airspeed and cannot guarantee V2+15 after an engine failure. The pilot must control pitch to acquire and maintain the displayed OEI climb speed, then trim as required after establishing the flight path.

## Unified aircraft state, stores, and validation hold

`AircraftState` is the only production source for variant, station stores, internal and external fuel, launch and recovery zero-fuel weights, launch and recovery gross weights, and drag state. The normal workflow has no independent takeoff or landing gross-weight input. An advanced DCS gross-weight override remains for controlled testing; its explicit adjustment is carried into recovery.

The published F-14B empty weight is 41,780 lb. F-14B(U) currently retains that baseline until a controlled DCS payload-delta test establishes a supported variant difference. Crew and operating items default to a documented 440 lb project assumption. Internal fuel capacity is 16,200 lb. The two FPU-1 tanks add 3,600 lb external fuel capacity.

Takeoff gross weight now captures store and fuel weight but the takeoff model still lacks a validated store-specific aerodynamic correction. When external stores are selected, the app therefore labels the takeoff result `PLANNING HOLD` and suppresses a GO determination. Hot/high reduced-thrust conditions are also held. The Henderson fuel-flow observations are used locally, but the thrust and runway-distance correction still does not reproduce the +40 C takeoff tests. Provisional values remain visible for controlled calibration and are not presented as validated runway guidance.

The corrected 62,000 lb MANEUVER run records rotation at 143 KIAS and 5401 ft, followed by liftoff at 6101 ft. This is a 700 ft rotation segment. It is an all-engines-operating liftoff observation and must not be mislabeled as accelerate-go or 50-ft distance.

The pilot does not enter a drag index. `data/f14_stores.csv` provides one structured inventory for Heatblur stations 1A, 1B, 2, 3, 4, 5, 6, 7, 8B, and 8A. It records per-station quantity, F-14B or F-14B(U) compatibility, adapter family, nominal mass, external fuel capacity, expendability, jettisonability, provisional drag, and separate source classes. Heatblur SCL presets populate this same station model rather than bypassing it.

Nominal store masses remain `NOMINAL_PLANNING`. Rack, pallet, and adapter masses remain explicit `UNRESOLVED_DCS_DELTA` values of zero until a controlled DCS payload-delta matrix exists. The model warns about both conditions and never creates an undocumented adapter-mass credit.

Station selections generate low-confidence internal model drag units for climb and cruise calculations. These units are engineering estimates, not a released F-14 drag-index table. NAVAIR Figure 14-1 directly identifies only two configuration references: DI 8 for four AIM-7 and DI 100 for six AIM-54 plus two 267-gallon tanks. The app recognizes those exact combinations but does not invent a unique per-store decomposition from two aggregate points.

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
- guarded distance to cruise altitude
- conservative two-engine fuel burned to cruise altitude
- the number of altitude segments that cannot meet the selected gradient gate

The legacy F110 deck supplies only the per-engine fuel-flow estimate. The low-order F-14 aerodynamic polar is no longer used to predict operational climb rate. Both schedules are ESTIMATED DCS planning products and are biased toward time, distance, and fuel margin.

NAVAIR Figure 14-1 is an airspeed-indicator-failure figure. Its 6.0-to-9.5-unit MIL-climb values are retained only as alternate AOA cues and do not validate the internal 250/300/M0.72 test schedule, rate, time, distance, or fuel.

## Landing

Landing ground roll uses direct/interpolated values from `f14_landing_natops_full.csv`.

On-speed AOA is 15 units. On-speed IAS uses the flight-test curves in NAVAIR 01-F14AAP-1 Figure 11-8 for 20-degree wing sweep and all drag indexes. The app displays both normal DLC-neutral IAS and DLC-stowed IAS with the chart's +/-4 kt tolerance.

Landing fuel quick-reference calculations use:

- 60,000 lb maximum field landing gross weight
- 51,800 lb F-14B or 54,000 lb modified F-14B(U) carrier/FCLP planning limit
- synchronized launch zero-fuel weight for the all-stores-retained reference
- synchronized expected-recovery zero-fuel weight after retained, expended, and jettisoned station selections
- 16,200 lb internal fuel capacity plus up to 3,600 lb in selected external tanks
- recovery fuel capacity reduced when a tank is planned jettisoned

Maximum fuel values are rounded down to the nearest 100 lb. Unresolved rack and adapter mass is not silently credited.

## Cruise

Optimum altitude and Mach use the legacy cruise table. Raw altitude is rounded to the nearest 1,000 ft usable flight level before the display condition is calculated.

The low-order aerodynamic model determines required thrust at the rounded flight level. The F110 deck is then searched for the lowest modeled dry RPM that meets drag. Because that one-percent equilibrium result is not a cockpit calibration, the app rounds the initial RPM upward to 5-percent increments, recomputes fuel flow at that setting, and rounds fuel flow upward to 250 PPH per engine. Specific range and endurance use the two-engine aircraft total internally and remain estimates.

No maximum-range, normal, or high-speed mode is promoted as validated. NAVAIR Figure 14-1 is an airspeed-indicator-failure figure; its 8-unit optimum-altitude value is an alternate AOA cue and does not validate the legacy table's altitude, Mach, FF, or RPM.

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
