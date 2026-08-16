from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .data import read_csv, require_columns
from .types import Runway


@dataclass(frozen=True)
class AirportSelection:
    map_name: str
    airport_name: str
    runway_end: str
    runway: Runway
    database_note: str


class AirportDatabase:
    REQUIRED = {
        "map", "airport_name", "runway_end", "heading_deg", "length_ft",
        "tora_ft", "toda_ft", "asda_ft", "threshold_elev_ft",
        "opp_threshold_elev_ft", "slope_percent", "notes",
    }

    def __init__(self, data_dir: Path | str | None = None):
        self.df = read_csv("dcs_airports.csv", data_dir)
        require_columns(self.df, self.REQUIRED, "dcs_airports.csv")

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
        return AirportSelection(map_name, airport_name, self._runway_key(runway_end), runway, note)
