#!/usr/bin/env python3
"""Print the maintained F-14 EFB validation battery for review or CI."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.f14perf.validation import run_validation_battery


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=("csv", "markdown"), default="markdown")
    args = parser.parse_args()
    outcomes = run_validation_battery()
    if args.format == "csv":
        print(outcomes.to_csv(index=False), end="")
    else:
        print(outcomes.to_markdown(index=False))
    return 0 if bool(outcomes["status_match"].all()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
