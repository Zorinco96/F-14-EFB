# EFB UX benchmark, 2026-08-16

> Historical baseline. The current interface audit is `EFB_UX_BENCHMARK_2026-09-01.md`.

## Benchmark set

The interface was compared with four common EFB patterns:

| Product | Useful pattern | Applied to F-14 EFB |
| --- | --- | --- |
| [ForeFlight Mobile](https://foreflight.com/products/foreflight-mobile/) | Fast form-based planning, integrated performance, phase-ready flight package | One setup rail feeding a Quick Plan and phase tabs |
| [Jeppesen FliteDeck Pro](https://ww2.jeppesen.com/navigation-solutions/flitedeck-pro/) | Contextual information with fewer interactions and integrated flight-plan views | Phase-specific Takeoff, Enroute, Recovery, Tools, and Kneeboard views |
| [Garmin Pilot](https://www.garmin.com/en-US/aviation/garminpilot/overview/) | Central trip planning and clear readiness/status cues | Persistent departure status plus one primary cue per phase |
| [Navigraph Charts](https://navigraph.com/products/charts) | Relevant material grouped around the active flight instead of exposed as a data catalog | Raw methods and observation tables moved to Data expanders |

## Findings and implemented changes

| Finding | UX or safety effect | Change |
| --- | --- | --- |
| Five expanded setup groups made every input look equally important | Slow scan and weak hierarchy | Mission essentials, departure runway, weather, and takeoff setup remain primary; aircraft/loadout and advanced policy are collapsed |
| RPM was displayed as the commanded takeoff setting | Conflicted with the requested cockpit technique and NATOPS engine indications | FF is now the large primary takeoff cue; RPM and nozzle are secondary cross-checks |
| A positive `LEGACY FIT` status could be read as dispatch-ready | Overstated data confidence | Replaced with `REFERENCE ONLY`; invalid domains use `PLANNING HOLD` |
| V1 looked operational despite an unvalidated numerical sweep | Could imply rejected-takeoff or OEI authority the model does not have | V1 is withheld from the main interface and kneeboard |
| DCS airport selection assumed physical full length | Hidden geometry error at runway-start spawns | Added Full length, DCS runway start, and Custom available-distance entries |
| Low-confidence climb checkpoints dominated the enroute page | Model detail outranked verified flying technique | NATOPS AOA technique is primary; detailed engineering checkpoints are collapsed |
| Cruise altitude, Mach, FF, and RPM looked source-backed | The source citation was invalid | Renamed to Legacy cruise trial, added 8-unit AOA technique, and labeled power data uncalibrated |
| Repeated raw tables competed with mission decisions | Higher interaction and visual density | Raw observations, attached Tacview motion, and method detail stay in the Data view |

## Resulting information hierarchy

1. Quick Plan: departure status, FF thrust set, takeoff references, recovery cue, and mission fuel.
2. Takeoff: FF-first engine setting, secondary engine cross-checks, guarded speeds, trial trim, runway planning, and correlated Tacview evidence.
3. Enroute: NATOPS AOA techniques first, conservative time/fuel allowance second, model checkpoints on demand.
4. Recovery: 15-unit AOA and Figure 11-8 IAS references first, legacy ground-roll estimate second.
5. Kneeboard: the same hierarchy in a compact DCS-ready card.
6. Data: provenance, validation status, raw observations, and parser-derived Tacview motion.

## Remaining UX work

- Add saved aircraft/mission profiles if the application gains persistent storage.
- Add a true preflight readiness checklist once required fields and validation states are stable.
- Add chart pinning only if departure, recovery, and range charts become available from verified unrestricted sources.
