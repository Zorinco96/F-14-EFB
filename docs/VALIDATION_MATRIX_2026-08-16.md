# Validation matrix, 2026-08-16

> Historical baseline. The current release matrix is `VALIDATION_MATRIX_2026-09-01.md`.

## Release rule

The app must fail closed when an input is outside the legacy takeoff grid, external-store takeoff drag is unmodeled, or hot/high reduced thrust is selected. A positive numerical margin is never labeled a GO result.

## Reconciled anchors

| Scenario | App result | External reference | Disposition |
| --- | ---: | ---: | --- |
| MIL takeoff engine indication | 10,100 PPH per engine primary; 95-104% N2 and 3-10% nozzle cross-checks | NAVAIR 01-F14AAP-1 sections 2.11.2-2.11.7 | Pass |
| Henderson 35L DCS runway start | 4,800 ft available | Attached Tacview start position reconciled with the published 6,501-ft runway endpoints, uncertainty about +/-100 ft | Pass; database correction added |
| Henderson, 62,000 lb, MAN, 95%, +40 C, two tanks/two AIM-9 | Legacy AEO estimate 4,447 ft; factored 5,114 ft; planning hold | Attached Tacview 4,853 ft from brake release to liftoff; user-reported 143-KIAS stick cue and 6.5 ANU heavy rotation | Raw estimate is 8.4% short; 1.15 factor is conservative; hold retained |
| Henderson correlated pitch response | 143 KIAS user rotation cue is not treated as Tacview pitch response | Tacview pitch response 161.1 KIAS, liftoff 165.0 KIAS | Pass; definitions separated |
| 54,000-lb field approach | 15 units AOA, about 139.7 KIAS DLC neutral, 130.6 KIAS DLC stowed, +/-4 kt | NAVAIR 01-F14AAP-1 Figure 11-8 flight-test chart | Pass |
| MIL climb technique | 6.0 units AOA at sea level increasing to 9.5 at combat ceiling | NAVAIR 01-F14AAP-1 Figure 14-1 | Pass; modeled rate/time remains allowance only |
| Cruise technique | 8.0 units AOA at optimum altitude | NAVAIR 01-F14AAP-1 Figure 14-1 | Pass; legacy altitude/Mach/FF/RPM remain unverified trial values |

## Environmental regression battery

The automated matrix covers standard, hot, high, cold, heavy, light, tailwind, and wet cases.

| Check | Required behavior |
| --- | --- |
| Weight | Vr and factored AEO distance increase from 58,000 to 72,000 lb |
| Temperature | +49 C factored AEO distance exceeds standard-day distance |
| Tailwind | A 10-kt tailwind increases factored AEO distance |
| Wet runway | Wet factored AEO and reject distances exceed dry values |
| Cold/light outside grid | 45,000 lb / -10 C is placed on planning hold |
| Hot/high/heavy outside grid | 75,000 lb / 5,000 ft / +35 C is placed on planning hold |
| External stores | Takeoff result is placed on planning hold until store drag is calibrated |
| Hot/high reduced thrust | Result is placed on planning hold even when FF is within the local observation band |

## Tacview telemetry limits

The attached files contain IAS, AGL, attitude, flap ratio, throttle ratio, and a non-standard normalized `FuelWeight` field. They do not contain per-engine `FuelFlowWeight` or `EngineRPM`. The audit therefore does not derive cockpit FF or RPM from Tacview throttle position or fuel-quantity slope.

Six complete Henderson takeoff sequences were extracted. Only one can be correlated to a fully described user test. The other five remain motion-only evidence because gross weight, center of gravity, trim, OAT, and cockpit engine indications are not encoded in the recordings.

The official [Heatblur tutorial index](https://f14.manuals.heatblur.se/tutorials.html) includes a front-seat startup, taxi, and takeoff video. It was reviewed as a procedural cross-check only. Video timing and visual runway position were not used as numeric calibration inputs because the controlled gross weight, weather, loadout, trim, and synchronized cockpit FF/RPM data needed for reconciliation are not published with the clip.

## Known holds

- The takeoff V1 sweep has no controlled engine-cut test basis. V1 is withheld from the operational interface and kneeboard.
- The public NATOPS flight manual points to the separate NAVAIR 01-F14AAP-1.1 performance supplement for takeoff charts. The repository's legacy V-speeds and runway grids have not been verified against that supplement.
- The prior cruise source citation was invalid because NAVAIR 01-F14AAP-1B is a pocket checklist and cannot contain the cited page. The citation has been removed and the data are labeled unverified.
- Climb rate, climb time/fuel, cruise altitude/Mach, cruise FF/RPM, landing ground roll, wet corrections, and external-store drag still require controlled DCS calibration before they can be promoted above reference or allowance status.
