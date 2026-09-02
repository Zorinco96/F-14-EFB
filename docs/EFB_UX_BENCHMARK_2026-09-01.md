# EFB UX benchmark, 2026-09-01

## Comparison set

The audit used current public product descriptions, not visual imitation or proprietary layouts.

| EFB pattern | Useful behavior | F-14 EFB application |
| --- | --- | --- |
| [ForeFlight](https://foreflight.com/products/foreflight-mobile/) | Aircraft profiles prepopulate performance data and reduce repeated entry | Aircraft variant, loadout preset, mission essentials, runway, and weather feed every phase |
| [ForeFlight Weight & Balance](https://foreflight.com/products/foreflight-mobile/weight-and-balance/) | Fast station-oriented load entry with integrated limits | Heatblur SCL presets plus station-by-station F-14 stores; recovery expendable credit is automatic |
| [Garmin Pilot](https://www.garmin.com/en-US/aviation/garminpilot/overview/) | At-a-glance flight planning with weather, airport, fuel, and performance context | Persistent four-card summary, consolidated planning state, and phase-specific details |
| [Garmin Pilot Flights](https://www.garmin.com/en-US/newsroom/press-release/aviation/garmin-pilot-update-introduces-new-flights-page-and-other-enhancements/) | One planning hub with compact cards and progressive disclosure | Overview plus Takeoff, Climb, Cruise, Landing, Tools, Mission Card, and Data tabs |
| [Navigraph Charts](https://navigraph.com/products/charts) | Flight-simulator-native planning and in-sim access | DCS airport/runway selection and 768 x 1024 kneeboard export |

## Findings implemented

| Previous friction or risk | Correction |
| --- | --- |
| Continuous reduced-power slider looked like an engine test bench | Replaced by AUTO, DERATE 3, DERATE 2, DERATE 1, and MIL |
| RPM could look like the primary thrust target | Large FF/engine result is primary; RPM is explicitly secondary |
| A reduced setting could be extrapolated into an unobserved atmosphere | AUTO uses only condition-calibrated indication references and retains MIL otherwise |
| Combined Enroute page mixed climb and cruise confidence | Climb and Cruise have separate phase tabs and separate source statements |
| Figure 14-1 AOA values looked like normal schedule validation | Corrected to airspeed-indicator-failure alternate cues |
| Loadout presets did not resemble DCS mission planning | Added Heatblur SCL-based BFM, CAP, strike, TARPS, and fleet-defense choices while retaining manual stations |
| One image export served both DCS and printing | Mission Card now exports both kneeboard PNG and one-page PDF |
| Raw observations competed with the pilot decision | Data tables and model JSON remain in the Data tab behind expanders |

## Current hierarchy

1. Persistent summary: departure state, FF/engine, Vr/V2, and recovery weight.
2. Overview: runway, weather, weight, V-speeds, thrust set, climb/cruise/recovery/fuel plan.
3. Takeoff: FF-first setting, secondary RPM/nozzle checks, speeds, trim, runway margins, and matching Tacview evidence.
4. Climb and Cruise: operational test targets first, confidence boundary immediately adjacent, checkpoints behind disclosure.
5. Landing: recovery fuel limits and approach/ground-roll references.
6. Mission Card: direct preview plus PNG and PDF export.
7. Data: provenance, observation registers, rating database, and raw model result.

## Remaining UX limitations

- Streamlit still constrains the interface compared with a native tablet EFB. The current design minimizes that constraint but does not emulate a certified vendor product.
- Gross weight remains a direct DCS entry. The app calculates expendable recovery credit but does not synthesize gross weight from partially filled external tanks or unknown rack/pod weights.
- A preflight readiness checklist should wait until reduced-rating and loadout takeoff envelopes are validated; adding one now would overstate dispatch authority.
