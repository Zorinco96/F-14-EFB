from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .data import DataError, read_csv, require_columns
from .types import Runway


@dataclass(frozen=True)
class AirportSelection:
    map_name: str
    airport_name: str
    runway_end: str
    runway: Runway
    database_note: str
    dcs_runway_start_tora_ft: float | None = None
    dcs_spawn_offset_ft: float | None = None
    runway_start_note: str = ""


class AirportDatabase:
    REQUIRED = {
        "map", "airport_name", "runway_end", "heading_deg", "length_ft",
        "tora_ft", "toda_ft", "asda_ft", "threshold_elev_ft",
        "opp_threshold_elev_ft", "slope_percent", "notes",
    }

    def __init__(self, data_dir: Path | str | None = None):
        self.df = read_csv("dcs_airports.csv", data_dir)
        require_columns(self.df, self.REQUIRED, "dcs_airports.csv")
        try:
            self.runway_starts = read_csv("dcs_runway_starts.csv", data_dir)
            require_columns(
                self.runway_starts,
                {
                    "map",
                    "airport_name",
                    "runway_end",
                    "dcs_runway_start_tora_ft",
                    "dcs_spawn_offset_ft",
                    "source_note",
                },
                "dcs_runway_starts.csv",
            )
        except (DataError, FileNotFoundError):
            self.runway_starts = pd.DataFrame()

    @property
    def maps(self) -> list[str]:
        return sorted(self.df["map"].dropna().astype(str).unique())

    def airports(self, map_name: str) -> list[str]:
        sub = self.df[self.df["map"] == map_name]
        return sorted(sub["airport_name"].dropna().astype(str).unique())

    @staticmethod
    def _runway_key(value) -> str:
        text = str(value).strip()
        try:
            number = int(float(text))
            if 0 <= number <= 99:
                return f"{number:02d}"
        except ValueError:
            pass
        return text.upper()

    def runway_ends(self, map_name: str, airport_name: str) -> list[str]:
        sub = self.df[(self.df["map"] == map_name) & (self.df["airport_name"] == airport_name)]
        return sorted({self._runway_key(v) for v in sub["runway_end"].dropna()})

    def get(self, map_name: str, airport_name: str, runway_end: str, condition: str = "DRY") -> AirportSelection:
        sub = self.df[
            (self.df["map"] == map_name)
            & (self.df["airport_name"] == airport_name)
            & (self.df["runway_end"].map(self._runway_key) == self._runway_key(runway_end))
        ]
        if sub.empty:
            raise ValueError("Selected runway was not found in the DCS airport database.")
        row = sub.iloc[0]
        length = float(row["length_ft"])
        start = row.get("threshold_elev_ft")
        end = row.get("opp_threshold_elev_ft")
        slope = row.get("slope_percent")
        if pd.isna(slope):
            if not pd.isna(start) and not pd.isna(end) and length > 0:
                slope = (float(end) - float(start)) / length * 100.0
            else:
                slope = 0.0
        elevation = None if pd.isna(start) else float(start)
        note = "" if pd.isna(row.get("notes")) else str(row.get("notes"))
        runway = Runway(
            name=f"{airport_name} RWY {runway_end}",
            heading_deg=float(row["heading_deg"]),
            tora_ft=float(row["tora_ft"] if not pd.isna(row["tora_ft"]) else length),
            toda_ft=float(row["toda_ft"] if not pd.isna(row["toda_ft"]) else length),
            asda_ft=float(row["asda_ft"] if not pd.isna(row["asda_ft"]) else length),
            slope_pct=float(slope),
            condition=condition.upper(),
            elevation_ft=elevation,
            notes=note,
        )
        start_tora = None
        spawn_offset = None
        start_note = ""
        if not self.runway_starts.empty:
            start_rows = self.runway_starts[
                (self.runway_starts["map"] == map_name)
                & (self.runway_starts["airport_name"] == airport_name)
                & (
                    self.runway_starts["runway_end"].map(self._runway_key)
                    == self._runway_key(runway_end)
                )
            ]
            if not start_rows.empty:
                start_row = start_rows.iloc[0]
                start_tora = float(start_row["dcs_runway_start_tora_ft"])
                spawn_offset = float(start_row["dcs_spawn_offset_ft"])
                start_note = str(start_row["source_note"])
        return AirportSelection(
            map_name,
            airport_name,
            self._runway_key(runway_end),
            runway,
            note,
            start_tora,
            spawn_offset,
            start_note,
        )
