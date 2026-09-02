from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .data import DEFAULT_DATA_DIR, DataError, read_csv, require_columns


@dataclass(frozen=True)
class ModelAuthority:
    domain: str
    production_model: str
    status: str
    baseline_source: str
    dcs_validation: str
    production_data: str
    notes: str


REQUIRED_COLUMNS = {
    "domain",
    "production_model",
    "status",
    "baseline_source",
    "dcs_validation",
    "production_data",
    "notes",
}


def authority_registry(data_dir: Path | str | None = None) -> dict[str, ModelAuthority]:
    base = Path(data_dir) if data_dir is not None else DEFAULT_DATA_DIR
    df = read_csv("model_authority.csv", base)
    require_columns(df, REQUIRED_COLUMNS, "model_authority.csv")
    if df["domain"].duplicated().any():
        duplicates = sorted(df.loc[df["domain"].duplicated(), "domain"].astype(str))
        raise DataError(f"model_authority.csv contains duplicate domains: {duplicates}")
    return {
        str(row.domain): ModelAuthority(
            domain=str(row.domain),
            production_model=str(row.production_model),
            status=str(row.status),
            baseline_source=str(row.baseline_source),
            dcs_validation=str(row.dcs_validation),
            production_data=str(row.production_data),
            notes=str(row.notes),
        )
        for row in df.itertuples(index=False)
    }


def domain_status(domain: str, data_dir: Path | str | None = None) -> str:
    registry = authority_registry(data_dir)
    if domain not in registry:
        raise KeyError(f"No production authority declared for {domain}")
    return registry[domain].status
