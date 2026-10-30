"""Load control definitions and run them.

A control is one SQL file in controls/. Its header (YAML inside a /*--- ---*/
comment) says what it checks, who owns it, how severe a failure is and how to
triage it. The query returns one row per item checked:

    lei, related_lei, is_exception, detail

The engine never interprets the SQL; adding a control is adding a file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
import pandas as pd
import yaml

HEADER = re.compile(r"/\*---\n(.*?)\n---\*/", re.S)
REQUIRED_KEYS = {"id", "name", "dimension", "severity", "owner", "description", "impact", "runbook"}
DIMENSIONS = {"completeness", "accuracy", "validity", "consistency", "uniqueness", "timeliness"}
SEVERITIES = ["critical", "high", "medium", "low"]
COLUMNS = ["lei", "related_lei", "is_exception", "detail"]
SAMPLE_SIZE = 25  # exceptions kept per control for the write-up; counts always cover everything


@dataclass(frozen=True)
class Control:
    id: str
    name: str
    dimension: str
    severity: str
    owner: str
    description: str
    impact: str
    runbook: list[str]
    sql: str = field(repr=False)
    path: Path | None = None

    @property
    def query(self) -> str:
        return HEADER.sub("", self.sql).strip().rstrip(";")


@dataclass
class Result:
    control: Control
    checked: int
    exceptions: int
    sample: pd.DataFrame

    @property
    def rate(self) -> float:
        return self.exceptions / self.checked if self.checked else 0.0


def parse_control(path: Path) -> Control:
    text = path.read_text()
    match = HEADER.search(text)
    if not match:
        raise ValueError(f"{path.name}: missing /*--- ---*/ header")
    meta = yaml.safe_load(match.group(1))
    missing = REQUIRED_KEYS - meta.keys()
    if missing:
        raise ValueError(f"{path.name}: header is missing {sorted(missing)}")
    if meta["dimension"] not in DIMENSIONS:
        raise ValueError(f"{path.name}: unknown dimension {meta['dimension']!r}")
    if meta["severity"] not in SEVERITIES:
        raise ValueError(f"{path.name}: unknown severity {meta['severity']!r}")
    if not path.stem.startswith(meta["id"] + "_"):
        raise ValueError(f"{path.name}: file name must start with its id {meta['id']}")
    return Control(**{k: meta[k] for k in REQUIRED_KEYS}, sql=text, path=path)


def load_controls(directory: Path) -> list[Control]:
    controls = [parse_control(p) for p in sorted(directory.glob("E*.sql"))]
    ids = [c.id for c in controls]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate control ids")
    return controls


def run_control(con: duckdb.DuckDBPyConnection, control: Control) -> Result:
    con.execute(f"create or replace temp view _result as {control.query}")
    columns = [d[0] for d in con.execute("select * from _result limit 0").description]
    if columns != COLUMNS:
        raise ValueError(f"{control.id}: query must return {COLUMNS}, got {columns}")
    checked, exceptions = con.execute(
        "select count(*), count(*) filter (where is_exception) from _result"
    ).fetchone()
    sample = con.execute(
        f"select lei, related_lei, detail from _result where is_exception "
        f"order by lei, related_lei limit {SAMPLE_SIZE}"
    ).df()
    return Result(control, checked, exceptions, sample)


def run_all(con: duckdb.DuckDBPyConnection, controls: list[Control]) -> list[Result]:
    return [run_control(con, c) for c in controls]
