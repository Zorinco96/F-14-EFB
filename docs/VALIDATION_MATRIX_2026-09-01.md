# Validation matrix, 2026-09-01

## Release rules

- No routine takeoff afterburner path exists.
- Continuous takeoff RPM and FF inputs are rejected.
- AUTO searches only discrete ratings and requires a condition-calibrated cockpit indication.
- AUTO retains MIL when reduced-rating indication evidence is missing.
- A positive runway margin never overrides a planning hold.
- V1 remains withheld until controlled engine-cut testing exists.
- External-store takeoff results remain on hold until aerodynamic penalties are calibrated.

## Rating evidence

| Rating | Near-SL/ISA FF per engine | RPM cross-check | Current use |
| --- | ---: | ---: | --- |
| DERATE 3 | 3,400 PPH | approximately 85% N2 | UP only; static indication evidence |
| DERATE 2 | 4,800 PPH | approximately 90% N2 | UP/MANEUVER; static indication evidence |
| DERATE 1 | 7,000 PPH | approximately 95% N2 | UP/MANEUVER; limited takeoff evidence |
| MIL | approximately 10,100 PPH | 95-104% N2; nozzle 3-10% | Published normal indication and fail-safe dry setting |

At the Henderson observation condition, DERATE 1 uses 5,250 PPH/engine at approximately 95% N2. This is a local cockpit-indication reference. It does not prove equivalent delivered thrust.

## Maintained scenario battery

The battery is defined in `data/validation_scenarios.csv` and executed by `src/f14perf/validation.py`.

| Case | Expected state | Selected rating | FF/eng | Vr/V2 | Factored AEO distance | Climb time/distance/fuel | Disposition |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| Light/cold/long | REFERENCE ONLY | MIL | 10,100 | 140/153 | 2,287 ft | 24 min / 160 NM / 6,500 lb | Trend pass |
| ISA AUTO | REFERENCE ONLY | DERATE 2 | 4,800 | 159/172 | 6,530 ft | 23 min / 150 NM / 6,000 lb | Discrete selection pass |
| ISA MIL | REFERENCE ONLY | MIL | 10,100 | 159/172 | 3,205 ft | 23 min / 150 NM / 6,000 lb | Comparison anchor |
| Hot sea-level/heavy | REFERENCE ONLY | MIL | 10,100 | 168/181 | 5,375 ft | 22 min / 140 NM / 6,000 lb | Edge-grid pass |
| Hot/high/heavy | REFERENCE ONLY | MIL | 10,100 | 168/181 | 10,545 ft | 22 min / 140 NM / 6,000 lb | Conservative altitude trend pass |
| Short runway | LIMIT EXCEEDED | MIL fallback | 10,100 | 159/172 | 3,205 ft on 2,500 ft | 23 min / 150 NM / 6,000 lb | Limit gate pass |
| 10-knot tailwind | REFERENCE ONLY | MIL | 10,100 | 159/172 | 3,838 ft | 23 min / 150 NM / 6,000 lb | Exceeds ISA MIL distance |
| Heavy CAP | PLANNING HOLD | MIL | 10,100 | 165/178 | 3,786 ft | 27 min / 175 NM / 7,500 lb | Store-drag hold pass |
| Medium strike | PLANNING HOLD | MIL | 10,100 | 149/163 | 3,545 ft | 26 min / 165 NM / 7,000 lb | Store-drag hold pass |
| Two tanks/two AIM-9 | PLANNING HOLD | MIL | 10,100 | 151/164 | 2,893 ft | 26 min / 165 NM / 7,000 lb | Store-drag hold pass |
| Henderson Tacview | PLANNING HOLD | DERATE 1 | 5,250 | 143/155 | 5,114 ft | 26 min / 165 NM / 7,000 lb | Unfactored estimate 4,447 ft, 8.4% below 4,853-ft Tacview liftoff |

Climb and cruise columns are scenario outputs, not external known values. Their purpose in this battery is regression, trend, unit, and safety-state validation. They are not promoted to NATOPS accuracy.

## External anchors

| Anchor | Known value | Result |
| --- | --- | --- |
| MIL engine indication | approximately 10,100 PPH/engine; 95-104% N2; nozzle 3-10% | Exact release gate |
| Batumi static EIG sweep | 3,400/4,800/7,000 PPH at approximately 85/90/95% N2 | Exact rating-database gates |
| Henderson runway-start distance | approximately 4,800 ft available, about +/-100 ft | Airport database gate |
| Henderson correlated liftoff | 4,853 ft from brake release | Unfactored model within 10%; factored result exceeds available runway; hold retained |
| Henderson pitch timing | 143-KIAS user stick cue; 161.1-KIAS Tacview pitch response | Definitions remain separate |
| 54,000-lb on-speed chart | approximately 139.7 KIAS DLC neutral and 130.6 KIAS DLC stowed, +/-4 kt | Exact landing regression gates |

## Source-boundary findings

- Tacview carries no per-engine FF or RPM fields in the attached recordings. It cannot calibrate the engine-setting database.
- NAVAIR 01-F14AAP-1 points takeoff and full performance work to the separate performance supplement. The public flight manual alone cannot validate the repository runway grids, best-climb schedule, or cruise mode tables.
- NAVAIR Figure 14-1 is an airspeed-indicator-failure reference. Its AOA values are not normal performance-chart validation.
- The legacy cruise table's former pocket-checklist citation was invalid. No maximum-range, normal, or high-speed cruise mode is labeled validated.

## Commands

```bash
python -m pytest -q
python tools/run_validation_matrix.py
```
