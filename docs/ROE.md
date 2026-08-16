# Rules of Engagement (ROE) - F-14 Performance Toolkit _V2

This document defines the standard permanent instructions ("Rules of Engagement") and the gold-standard Mission Card that all code, data, and features must adhere to.

## Permanent Instructions / Rules

- *NEVER truncate or trim files without prior permission.
- Source of truth is always the current github repository, and we will parse directly from it.
- *NO guessing of classes, methods, or features* when creating or refining code.
  - If a feature name or class is unclear, I must request the file directly from you.
- Solutions will undergo
    - Only when approved by you.
    - With the explicit readnack flow (like aviation IFR ).
- Commit process
    - Always pull current SHA for any file being updated.
    - Use one-file commits for traceability.
    - Audit on commits immediately after they are made.
    - Use base64 encoding for uploads to prevent data loss.
    - Use automated checks for truncation (file size, lost functionatality, etc.)
    - If a file is nearless or malformed, we report and proceed with fixes.
- Communication standard -- all execution instructions must be read-backed, confirmed, and only then executed.

- Test-Fix-Rerun Workflow
    - Always run tests locally in the GPT environment.
    - If a test fails, fix automatically, rerun the test, until passed or confirmed failure.
    - Explicit in log and commit messages when a repair is made.

## Gold-Standard Mission Card

The full mission card output structure before was locked in as our *game plan standard*. All models (/takeoff, /climb, /cruise, /landing) and calculations make reference to this output style.

The card includes:
- Takeoff Profiles with flaps, thrust, V-Speeds, climb gradients, trim.
- Climb Profiles at standard 100-6000f, with named strategies.
 - Cruise Profiles with best endurance, best range, efficiency.
- Landing Profiles with Vfs, Vac and go-aroun.
- Fuel analysis based on derated takeoff, military, AB, and economy profiles.
 - Bingo/Joker section with distance, reserves, and end-of-mission states.

All output makes must be aligned with this standard.