# F-14 EFB Development Plan

Authoritative revision: 2026-09-02

## Governing architecture

The production application follows one architectural rule:

> One aircraft state, one authoritative performance model, and one synchronized workflow.

`AircraftState` owns the selected variant, station loadout, recovery disposition, crew and operating items, internal fuel, external fuel, launch and recovery weights, launch and recovery drag states, and the advanced DCS weight adjustment. Takeoff, climb, cruise, recovery, mission fuel, and mission-card output must consume that state. Independent normal-workflow gross-weight, fuel, and drag inputs are prohibited.

The pilot workflow is:

1. Aircraft
2. Loadout
3. Fuel
4. Departure
5. Takeoff
6. Climb
7. Cruise
8. Recovery
9. Mission Card

## Source hierarchy

1. F-14 NATOPS establishes the aircraft-performance baseline, schedules, and limitations.
2. Controlled DCS testing captured in Tacview establishes how the Heatblur aircraft behaves in DCS.
3. A DCS correction may modify the NATOPS baseline only when the difference is material, repeatable, and documented.
4. Derived interpolation and conservative planning assumptions must remain identifiable.
5. Pilot impressions and isolated observations do not replace synchronized telemetry when Tacview can measure the behavior.

Every production domain is declared once in `data/model_authority.csv`. Every data file is classified in `data/data_inventory.csv`. Files identified as legacy, competing, continuous-derate, out of scope, or known bad remain outside the production calculation path.

## DCS loadout scope

`data/f14_stores.csv` is the single structured inventory. It represents the station quantities in the Heatblur DCS station matrix for stations 1A, 1B, 2, 3, 4, 5, 6, 7, 8B, and 8A. The current catalog includes:

- AIM-9L, AIM-9M, and training Sidewinder stores
- AIM-7E-2, AIM-7F, and AIM-7M
- AIM-54A Mk 47, AIM-54A Mk 60, and AIM-54C Mk 47
- FPU-1 tanks
- Mk-81, Mk-82, Mk-82AIR, Mk-82 Snake Eye, Mk-83, Mk-84, and Mk-20
- GBU-10, GBU-12, GBU-16, GBU-24, and F-14B(U) GBU-24E/B
- F-14B(U) GBU-31(V)2/B, GBU-31(V)4/B, and GBU-38
- BDU-33, LAU-10, ADM-141A, and SUU-25
- LAU-138, Smokewinder, TCTS, LANTIRN, TARPS, ECA, and ALQ-167
- explicit empty stations and empty Phoenix pallets

Station compatibility, per-station quantities, variant compatibility, forward and aft Phoenix-pallet relationships, external fuel capacity, and recovery disposition are enforced in the model. Standard Heatblur SCL patterns are presets that populate the station selector. They are not separate weight or drag categories.

## Weight and recovery state

The normal launch-weight relationship is:

```
published empty weight
+ crew and operating items
+ selected stores
+ documented adapter mass
+ internal fuel
+ external fuel
= calculated launch gross weight
```

The current published F-14B empty weight is 41,780 lb. The F-14B(U) uses that baseline until a controlled DCS payload-delta test establishes a supported variant difference. The default 440 lb crew and operating-items entry is a documented project assumption.

The loadout database deliberately records unresolved rack, pallet, and adapter mass as an unresolved zero delta. It does not invent missing weight. Nominal store masses and unresolved adapters produce visible engineering warnings. A controlled DCS rearm payload-delta matrix is required before those weights can be promoted.

Expected recovery configuration is derived from retained, expended, and jettisoned station selections. Planned tank jettison reduces the recovery fuel capacity. The advanced DCS gross-weight override is applied as one explicit adjustment and is carried into recovery so that it cannot silently desynchronize the mission.

## Reconciliation procedure

Each major performance domain must complete the same sequence:

1. Identify the relevant NATOPS source and chart conditions.
2. Reconstruct the NATOPS relationship without unrecorded correction.
3. Define a controlled DCS test that matches the NATOPS case.
4. Record the result through Tacview and synchronized cockpit indications when required.
5. Compare predicted and observed values using a declared tolerance.
6. Retain the NATOPS result when the difference is small.
7. Add a traceable DCS correction only when the difference is material and repeatable.
8. Run the full scenario battery before promoting the model status.

This applies to thrust and FF, RPM, takeoff acceleration and distance, rotation and liftoff, trim, AEO and OEI climb, climb schedules and phase totals, cruise speed and fuel flow, store drag, field landing, and carrier recovery behavior.

## Implementation sequence

1. Maintain discrete FF-first takeoff ratings and reject arbitrary RPM derates.
2. Complete controlled FF and RPM indication sweeps across pressure altitude and temperature.
3. Replace the guarded takeoff grid with a fully reconciled NATOPS and Tacview model.
4. Reconstruct the NATOPS climb schedules and validate time, distance, and fuel in DCS.
5. Reconstruct useful NATOPS cruise modes and validate speed, FF, RPM, range, and endurance.
6. Measure exact DCS store, rack, pallet, pod, and tank payload deltas.
7. Build a controlled per-configuration Tacview drag matrix.
8. Reconcile field landing distance and carrier recovery planning.
9. Complete phone, tablet, and desktop visual regression checks.
10. Promote held domains only after the automated validation tolerances pass.

Calculation integrity remains ahead of presentation work. The responsive pilot interface can expose a held result, but it cannot relabel that result as validated.

## Acceptance status

| Requirement | Current status | Release condition |
| --- | --- | --- |
| Complete station-based DCS inventory | Implemented from the Heatblur matrix | Recheck after relevant DCS inventory changes |
| Station restrictions and variant filters | Implemented for published relationships | Expand when Heatblur documents another enforced restriction |
| One synchronized aircraft state | Implemented | All new domains must accept `AircraftState` |
| Fuel and stores update launch weight | Implemented | Automated state and app tests remain green |
| Launch and expected recovery configuration | Implemented | Automated disposition and capacity tests remain green |
| Discrete FF-first thrust ratings | Implemented and condition-gated | Complete controlled environmental EIG matrix |
| Exact DCS store and adapter weights | Pending | Controlled payload-delta audit |
| Individual-store drag effects | Pending and explicitly guarded | NATOPS baseline plus repeatable Tacview matrix |
| Reconciled takeoff performance | Partial hold | NATOPS reconstruction plus AEO and OEI DCS matrix |
| Reconciled climb performance | Planning hold | NATOPS supplement reconstruction plus Tacview validation |
| Reconciled cruise performance | Planning hold | NATOPS reconstruction plus controlled DCS validation |
| Reconciled landing distance | Partial hold | Source re-digitization plus controlled DCS validation |
| Responsive pilot workflow | Implemented structurally | Browser-based phone, tablet, and desktop visual QA |
| Mission card from the shared state | Implemented | Export regression tests remain green |
| Conflicting legacy paths isolated | Implemented in inventory registry | Remove any new unregistered production data |

This phase is not performance-complete while a critical domain remains `PLANNING_HOLD`, `PARTIAL_HOLD`, `TRIAL_ONLY`, or reference-only. The open status is intentional and prevents architecture work from being mistaken for completed NATOPS and DCS reconciliation.
