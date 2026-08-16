from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = REPO_ROOT / "data"


class DataError(RuntimeError):
    pass


def _path(name: str, data_dir: Path | str | None = None) -> Path:
    base = Path(data_dir) if data_dir is not None else DEFAULT_DATA_DIR
    path = base / name
    if not path.exists():
        raise DataError(f"Required performance data file is missing: {path}")
    return path


def require_columns(df: pd.DataFrame, required: Iterable[str], name: str) -> None:
    missing = set(required) - set(df.columns)
    if missing:
        raise DataError(f"{name} is missing required columns: {sorted(missing)}")


@lru_cache(maxsize=32)
def _read_csv_cached(path_text: str) -> pd.DataFrame:
    return pd.read_csv(path_text)


def read_csv(name: str, data_dir: Path | str | None = None) -> pd.DataFrame:
    return _read_csv_cached(str(_path(name, data_dir))).copy()


def read_json(name: str, data_dir: Path | str | None = None) -> dict:
    with _path(name, data_dir).open("r", encoding="utf-8") as handle:
        return json.load(handle)
