# Source Registry

## Current simulation documentation

### Heatblur F-14 Tomcat manual

https://f14.manuals.heatblur.se/

Used for current DCS systems/configuration references including flap behavior, AOA presentation, fuel system, F110 integration, F-14B(U) features, carrier landing-weight context, and identification of the F-14B engine instrument group RPM indication as high-pressure compressor RPM (N2).

Relevant sections include:

- Technical Specifications
- Flight Controls & AFCS
- Engines and Fuel System
- Pilot Left Instrument Panel
- F-14B(U) Weapons / Loadout overview

## NASA primary research

NASA Technical Reports Server:

https://ntrs.nasa.gov/

Relevant F-14 research includes:

- low-speed high-lift aerodynamic investigation
- landing-configuration flight-test research
- Dryden F-14 aeromodel and asymmetric-thrust research

These reports are used to guide model structure and future validation. They are not treated as direct substitutes for the operational F-14B performance supplement.

## Repository legacy datasets

The following files predate v3 and are retained as project source data:

- `data/f14_perf.csv`
- `data/f14_landing_natops_full.csv`
- `data/f14_cruise_natops.csv`
- `data/F110_engine.csv`
- `data/f110_ff_to_rpm_knots.csv`
- `data/dcs_airports.csv`

Their original provenance is preserved in file labels/notes where available. V3 does not silently upgrade those labels into independent source verification.

`f110_ff_to_rpm_knots.csv` contains controlled DCS static fuel-flow/RPM observations. It is used only as a takeoff EIG reference and is labeled as calibrated rather than as a released F110 engine chart.
