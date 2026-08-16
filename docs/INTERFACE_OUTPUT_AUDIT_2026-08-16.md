# Interface and output audit, 2026-08-16

> Updated after the attached Tacview reconciliation. The current release findings are in `EFB_UX_BENCHMARK_2026-08-16.md` and `VALIDATION_MATRIX_2026-08-16.md`. Earlier runway-remaining-derived distances below have been replaced by measurements from brake release.

## Scope

This audit reviewed the deployed Streamlit workflow, the generated kneeboard, and every operational number shown for takeoff, climb, cruise, recovery, maneuvering, and mission fuel.

The governing rule is conservative DCS mission planning without converting an unverified model into a measured value.

## Interface findings and changes

| Finding | Risk | Implemented change |
| --- | --- | --- |
| `MEETS PLAN` and `LEGACY FIT` resembled GO determinations | Overstated confidence in legacy takeoff data | Replaced with `REFERENCE ONLY`; external stores, hot/high reduced thrust, and extrapolated cases remain `PLANNING HOLD` |
| Five-card header and repeated mission metrics were dense | Slower mission scan | Reduced header to four cards and consolidated enroute, recovery, and fuel into a mission-phase table |
| BINGO and JOKER were disconnected from the fuel inputs | Poor input grouping | Moved both into `Mission and fuel` |
| Planning policy was collapsed by default | Important assumptions were easy to miss | Planning policy now opens by default |
| Climb checkpoints dominated the enroute tab | Low-confidence details looked operationally primary | Moved checkpoints into a collapsed estimate panel |
| Kneeboard could overflow when a matching DCS test was added | Recovery or fuel data could be omitted | Added a compact seven-section layout and verified a full Henderson card at 768 x 1024 |

## Takeoff cross-check

The Henderson Tacviews exposed a material runway-entry error. The DCS runway-start spawn leaves approximately 4,800 ft available, not the full 6,501 ft physical runway length.

| Condition | Legacy AEO estimate | Factored estimate | Tacview AEO liftoff | Difference from raw estimate |
| --- | ---: | ---: | ---: | ---: |
| 62,000 lb, MANEUVER, 95%, +40 C, two tanks, two AIM-9 | 4,447 ft | 5,114 ft | 4,853 ft | +406 ft |

The Tacview value is motion distance from brake release to liftoff. The factored app value exceeds the approximately 4,800 ft available and the case remains on planning hold because external-store drag and hot/high reduced thrust are not validated.

The takeoff tab and kneeboard now show the matching DCS observation beside the unvalidated model result.

### Pitch trim

The current evidence is:

- 5.0 ANU UP was slightly heavy.
- 6.5 ANU MANEUVER was heavy.

The next controlled trial candidates are therefore:

- 5.5 ANU UP
- 7.0 ANU MANEUVER
- 0.0 ANU FULL remains an unvalidated baseline

These are trial settings, not an accepted schedule. Center of gravity was not recorded in the existing Henderson runs and remains a required test variable.

NAVAIR 01-F14AAP-1 documents a smooth rotation at the precomputed rotation speed and cautions that excessive aft stick can stall the tail surfaces and extend takeoff distance. It does not provide the DCS stabilator-trim schedule required by this project.

## Climb and cruise

### Climb

No verified F-14B climb chart is available in the repository. The guarded climb model remains a planning allowance and is no longer displayed with decimal precision:

- elapsed time rounds upward to a whole minute
- fuel rounds upward to 500 lb
- checkpoint rate and gradient estimates are collapsed by default

For the 65,000 lb clean baseline to FL340, the app now shows a 23-minute and 6,000 lb planning allowance. This is deliberately not labeled expected climb performance.

### Cruise

The cruise table remains only as an unverified trial target. Its prior source citation was invalid because NAVAIR 01-F14AAP-1B is a pocket checklist and cannot contain the cited page. KIAS is calculated from the atmosphere at the rounded trial flight level. The power model is not DCS-calibrated, so FF and RPM remain planning allowances.

For the 65,000 lb clean baseline, the revised reference is:

- FL340
- 245 KIAS / Mach 0.718
- initial model setting 80% RPM
- 2,250 PPH per engine

A controlled DCS cruise matrix is still required before altitude, Mach, RPM, or fuel flow can be treated as calibrated values. NATOPS Figure 14-1 supplies only the primary 8-unit AOA cruise technique for optimum altitude.

## Recovery cross-check

The previous square-root IAS estimate was removed. NAVAIR 01-F14AAP-1 Figure 11-8 is explicitly flight-test based and covers 15 units AOA, 20-degree wing sweep, all drag indexes, and landing weights from 40,000 through 60,000 lb.

At 54,000 lb the revised references are:

- normal DLC neutral: approximately 140 KIAS
- DLC stowed: approximately 131 KIAS
- chart tolerance: +/-4 kt

The same manual gives:

- 60,000 lb maximum field landing weight
- 54,000 lb maximum carrier/FCLP weight with AYC-679 or AYC-805
- 51,800 lb carrier/FCLP weight without those modifications, with 54,000 lb permitted when operational necessity dictates

The app keeps 54,000 lb as the F-14B(U) carrier-planning reference and now states the modification assumption.

## Maneuvering

The section remains limited to coordinated-turn geometry. Turn rate, radius, and time are mathematically valid for the entered speed and G, but the app does not claim that the selected G is aerodynamically available, sustainable, or structurally permitted.

## Fuel

The route input is now named `Cruise leg distance` because the model applies the entered distance entirely at cruise after computing climb separately. Total mission burn rounds upward to 500 lb. For the default 65,000 lb, 300-NM cruise-leg case, the revised planning burn is 10,500 lb and planned landing fuel is 5,500 lb from 16,000 lb start fuel.

## Primary references

- [Heatblur F-14 manual](https://f14.manuals.heatblur.se/)
- [Heatblur flight-model audit](https://heatblur.se/fmupdate/)
- [NAVAIR 01-F14AAP-1 public copy](https://server.3rd-wing.net/public/Bureau_VF31/Docs%20F-14%20r%C3%A9el/NAVAIR%2001-F14AAP-1%20-%20NATOPS%20Flight%20Manual%20-%20F-14B.pdf)

The separate F-14B/D performance supplement is still the highest-value missing source. Until it is independently verified and digitized, runway results outside observed DCS conditions, climb performance, and cruise power remain guarded rather than asserted.
