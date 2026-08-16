# DCS Calibration Test Plan

## Test discipline

Change one variable at a time. Record DCS version, F-14 variant, map, runway, gross weight, fuel, station-by-station stores, weather, flap configuration, RPM, and control technique. The test pilot does not need to provide a drag index.

Use the same control technique across repeated runs. Perform at least three runs for any point that will become a calibration anchor.

## Priority 1: true V1 / engine-failure field performance

For each configuration:

- UP
- MANEUVER
- FULL

At 65,000 lb, SL/15 C/calm/dry/MIL:

1. Choose candidate engine-failure speeds from approximately 0.85 Vr to Vr-3 in 5 kt increments.
2. At the test speed, fail one engine consistently using the same method.
3. Reject tests: record distance to full stop.
4. Continue tests: record distance to liftoff and to 50 ft AGL if practical.
5. Repeat each point three times.
6. Refine around the ASD/AGD crossover in 1 kt increments.

Repeat the final crossover test at 58,000 and 72,000 lb.

This dataset will replace the current estimated balanced-field V1 sensitivity.

## Priority 2: maneuver flaps

At weights:

- 58,000
- 65,000
- 72,000 lb

At pressure altitudes:

- 0
- 4,000
- 8,000 ft

At temperatures:

- approximately -7
- 15
- 32
- 49 C

Record:

- Vr
- liftoff distance
- 50-ft distance if practical
- reject distance at the selected V1
- initial climb gradient

This mirrors the structure of the existing UP/FULL table.

## Priority 3: reduced RPM

At 65,000 lb, SL/15 C:

UP:
- 85 through 100% in 2% increments

MANEUVER:
- 90 through 100% in 2% increments

FULL:
- 98 and 100%

Record:

- actual stabilized RPM
- fuel flow per engine
- Vr
- distance
- initial climb gradient

This will replace the current nonlinear reduced-thrust assumption.

## Priority 4: pre-roll stabilator trim and OEI V2+15

At 55,000, 65,000, and 75,000 lb, test each takeoff flap configuration on a standard-day, calm-wind departure:

1. Set pitch trim 000 before commencing the takeoff roll.
2. Record the generated Vr, V2, and OEI V2+15 target.
3. Verify neutral-stick stabilator position before brake release. With full flaps, compare against the documented integrated-trim check of approximately 3 degrees trailing-edge up.
4. Rotate using the same control technique on every run.
5. Fail one engine consistently after rotation, select gear up, and set MILITARY thrust on the operating engine.
6. Control pitch to acquire V2+15 and record the additional stick force and trim input required after liftoff.
7. Record distance, height, actual IAS, climb gradient, yaw-control margin, pitch-trim command, and stabilator position if available.
8. Repeat each condition three times.

The current app schedule remains 6.0 ANU MANEUVER, 3.0 ANU UP, and 0.0 ANU FULL while testing continues. Do not treat the former 5.0 to 7.0 ANU MANEUVER range as an accepted band. In the latest 62,000 lb F-14B(U) test with two external tanks and two AIM-9s, 5.0 ANU UP was slightly heavy and 6.5 ANU MANEUVER was heavy. The next controlled candidates are 5.5 ANU UP and 7.0 ANU MANEUVER, changing only 0.5 ANU per run. The rotation acceptance criterion is a smooth rotation initiated at V2 with normal aft-stick pressure, no excessive backpressure, and no uncommanded pitch-up. Record the best setting and acceptable band by flap configuration, center of gravity, and loadout. Evaluate the separate transition to the V2+15 OEI climb condition after liftoff.

## Priority 5: climb

At 60,000 and 70,000 lb:

- altitudes every 5,000 ft through 30,000 ft
- 200 / 225 / 250 / 300 KIAS where applicable
- MIL and selected reduced RPMs

Record steady:

- TAS/Mach
- fuel flow
- vertical speed
- aircraft configuration

For each weight, fly the generated 95% dry and MIL planning schedules from 1,000 ft to the rounded cruise flight level. Use 250 KIAS through 10,000 ft, then 300 KIAS to the Mach 0.72 crossover. Record elapsed time, fuel at profile start, fuel at 10,000 ft, and fuel at level-off. Record fuel flow per engine. Compare observed segment rates and total fuel against the guarded schedule before changing the planning allowances.

## Priority 6: cruise

At 50/60/70k gross weight and representative drag indices:

- fly the table optimum altitude and M0.718
- stabilize for at least one minute
- record fuel flow and required throttle/RPM
- repeat one altitude above and below optimum

This validates whether the legacy optimum table is consistent with current DCS and calibrates the fuel model.

## Priority 7: landing

At 45/50/55k landing weight:

- full flaps
- SL/15 C calm
- dry runway

Record:

- stabilized on-speed IAS at 15 units AOA
- threshold speed
- touchdown speed
- ground roll with consistent braking technique

Then test headwind and wet-surface effects separately.

## Data format

Store every raw run, not only averages. Recommended columns:

`date,dcs_version,variant,map,airport,runway,weight_lb,cg_pct_mac,station_loadout,derived_model_drag_units,pa_ft,oat_c,wind_dir,wind_kt,condition,flaps,takeoff_trim_anu,thrust_mode,thrust_setting_basis,rpm_pct,v1_kt,vr_kt,v2_kt,vfs_kt,oei_target_kt,trim_command_after_liftoff,stabilator_position,engine_failure_kt,decision,rotation_distance_ft,liftoff_distance_ft,liftoff_distance_min_ft,liftoff_distance_max_ft,height50_distance_ft,climb_gradient_ft_nm,roc_fpm,fuel_flow_left,fuel_flow_right,notes`

The maintained raw run log is `data/dcs_takeoff_test_log.csv`. Blank fields mean not reported, not zero. Derived distances are explicitly labeled and app-calculated values must never be entered as measured DCS results.

The engine observation register is `data/dcs_engine_observations.csv`. Keep throttle-setting technique, observed RPM, and left/right fuel flow as separate fields. Do not convert a percentage of available thrust into RPM unless the cockpit RPM was actually observed.
