# Source Registry

## Current simulation documentation

### Heatblur F-14 Tomcat manual

https://f14.manuals.heatblur.se/

Direct configuration references:

- Station matrix: https://f14.manuals.heatblur.se/f14ab/stores/overview.html
- F-14B(U) weapons and SCL overview: https://f14.manuals.heatblur.se/f14bu/weapons/overview.html
- Fuel system: https://f14.manuals.heatblur.se/f14ab/systems/engines_and_fuel_systems/fuel_system.html
- Technical specification: https://f14.manuals.heatblur.se/intro/specification.html

Used for current DCS systems/configuration references including flap behavior, AOA presentation, fuel system, F110 integration, F-14B(U) features, carrier landing-weight context, and identification of the F-14B engine instrument group RPM indication as high-pressure compressor RPM (N2).

Relevant sections include:

- Technical Specifications
- Flight Controls & AFCS
- Engines and Fuel System
- Pilot Left Instrument Panel
- F-14B(U) Weapons / Loadout overview
- Official tutorial index, including the front-seat startup, taxi, and takeoff video

The Heatblur fuel-system table gives 16,200 lb internal fuel and 3,600 lb external fuel, or 19,800 lb total. The technical specification gives 41,780 lb empty weight and 74,349 lb maximum weight for the F-14B. The F-14B(U) loadout documentation identifies 54,000 lb as the maximum carrier landing weight used for trap-fuel planning. Its weapons overview supplies the AAW, AG, TARPS, training, and special Standard Conventional Loadout count patterns used by the preset menu.

The official Heatblur tutorial video was used as a procedural presentation cross-check, not as a numerical calibration source. Its published context does not provide a controlled weight/weather/loadout matrix or machine-readable cockpit FF/RPM series, so no performance database values were fitted to video timing or visual runway position.

### F-14 gross-weight reference

The NAVAIR F-14D flight-manual gross-weight quick-reference lists 60,000 lb for field landing and 54,000 lb for carrier/FCLP landing. F-14 EFB uses these as DCS planning limits for the F-14B(U) recovery quick reference. The app rounds calculated maximum fuel down to 100 lb and still requires the user to verify actual DCS gross weight.

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
- `data/f110_takeoff_ff_environment.csv`
- `data/f110_takeoff_ratings.csv`
- `data/validation_scenarios.csv`
- `data/dcs_engine_observations.csv`
- `data/dcs_takeoff_test_log.csv`
- `data/tacview_takeoff_motion.csv`
- `data/dcs_runway_starts.csv`
- `data/dcs_airports.csv`

Their original provenance is preserved in file labels/notes where available. V3 does not silently upgrade those labels into independent source verification.

`f110_ff_to_rpm_knots.csv` contains the user-confirmed Batumi static fuel-flow/RPM observations. `f110_takeoff_ff_environment.csv` contains the narrow Henderson +40 C aggregate used from 95 through 98% RPM. The two raw observation registers retain individual engine and takeoff runs. These values are labeled as DCS-calibrated observations rather than as released F110 or F-14 performance charts.

`f110_takeoff_ratings.csv` defines the four standardized takeoff choices. The three reduced rows must match exact Batumi observation knots; MIL retains the NAVAIR normal indication. `validation_scenarios.csv` is a maintained test-case registry, not a source of performance truth.

The attached Tacview files were parsed with `tools/analyze_tacview.py`. They provide motion and configuration telemetry but no per-engine fuel-flow or engine-RPM fields. `dcs_runway_starts.csv` records the approximately 4,800 ft available from the Henderson 35L DCS runway-start spawn, with about +/-100 ft uncertainty.

The prior cruise-table citation to NAVAIR 01-F14AAP-1B page 241 was removed because that pocket checklist does not contain the claimed page. Cruise altitude, Mach, FF, and RPM remain unverified trial outputs.

NAVAIR 01-F14AAP-1 Figure 14-1 appears in the airspeed-indicator-failure procedure. Its climb and cruise AOA values are alternate cues for that failure context. They do not validate the normal climb schedule, time/distance/fuel, optimum cruise level, cruise Mach, FF, or RPM.

## Production data governance

`data/model_authority.csv` declares the single production model for aircraft weight, inventory, store weight, drag, thrust, RPM, takeoff, trim, climb, cruise, landing, and mission fuel. `data/data_inventory.csv` classifies every repository data file. Conflicting continuous-derate fits, takeoff overlays, refusal-distance tables, malformed aerodynamic data, and out-of-scope TF30 data are isolated from the production path rather than averaged into active results.

`data/f14_stores.csv` separates inventory provenance (`HEATBLUR_DCS`), store-mass provenance (`NOMINAL_PLANNING`), adapter-mass provenance (`UNRESOLVED_DCS_DELTA`), and drag provenance (`ASSUMPTION`). Exact DCS payload-delta and controlled Tacview drag matrices remain required before those guarded fields can be promoted.
