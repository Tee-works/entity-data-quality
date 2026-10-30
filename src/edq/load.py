"""Load the GLEIF golden copy into DuckDB.

GLEIF publishes three full files three times a day (goldencopy.gleif.org):
LEI-CDF (the entities), RR-CDF (relationships between them) and Reporting
Exceptions (why an entity reports no parent). Each zip is streamed straight
into Parquet with only the columns the controls use, so the 4 GB of CSV never
lands on disk.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import duckdb
import requests

LATEST = "https://goldencopy.gleif.org/api/v2/golden-copies/publishes/latest"
FILES = {"lei2": "entities", "rr": "relationships", "repex": "exceptions"}

COLUMNS = {
    "entities": {
        "LEI": "lei",
        "Entity.LegalName": "legal_name",
        "Entity.LegalAddress.Country": "legal_address_country",
        "Entity.RegistrationAuthority.RegistrationAuthorityID": "ra_id",
        "Entity.RegistrationAuthority.RegistrationAuthorityEntityID": "ra_entity_id",
        "Entity.LegalJurisdiction": "jurisdiction",
        "Entity.EntityCategory": "category",
        "Entity.LegalForm.EntityLegalFormCode": "legal_form",
        "Entity.EntityStatus": "entity_status",
        "Entity.EntityCreationDate": "entity_created",
        "Entity.EntityExpirationDate": "entity_expired",
        "Entity.EntityExpirationReason": "expiration_reason",
        "Entity.SuccessorEntity.1.SuccessorLEI": "successor_lei",
        "Entity.SuccessorEntity.1.SuccessorEntityName": "successor_name",
        "Registration.InitialRegistrationDate": "initial_registration",
        "Registration.LastUpdateDate": "last_update",
        "Registration.RegistrationStatus": "registration_status",
        "Registration.NextRenewalDate": "next_renewal",
        "Registration.ManagingLOU": "managing_lou",
        "Registration.ValidationSources": "validation_sources",
        "ConformityFlag": "conformity_flag",
    },
    "relationships": {
        "Relationship.StartNode.NodeID": "child_lei",
        "Relationship.EndNode.NodeID": "parent_lei",
        "Relationship.EndNode.NodeIDType": "parent_id_type",
        "Relationship.RelationshipType": "rel_type",
        "Relationship.RelationshipStatus": "rel_status",
        "Relationship.Period.1.startDate": "period1_start",
        "Relationship.Period.1.endDate": "period1_end",
        "Relationship.Period.1.periodType": "period1_type",
        "Relationship.Qualifiers.1.QualifierCategory": "accounting_standard",
        "Registration.InitialRegistrationDate": "rr_initial_registration",
        "Registration.LastUpdateDate": "rr_last_update",
        "Registration.RegistrationStatus": "rr_registration_status",
        "Registration.NextRenewalDate": "rr_next_renewal",
        "Registration.ManagingLOU": "rr_managing_lou",
        "Registration.ValidationSources": "rr_validation_sources",
    },
    "exceptions": {
        "LEI": "lei",
        "Exception.Category": "category",
        "Exception.Reason.1": "reason",
    },
}


def latest_publish() -> dict:
    data = requests.get(LATEST, timeout=60).json()["data"]
    return {
        "publish_date": data["publish_date"],
        "files": {FILES[k]: data[k]["full_file"]["csv"] for k in FILES},
    }


def to_parquet(zip_path: Path, table: str, out: Path) -> None:
    """Stream one golden-copy zip into a Parquet file of the columns we keep."""
    select = ", ".join(f'"{src}" as {dst}' for src, dst in COLUMNS[table].items())
    unzip = subprocess.Popen(["unzip", "-p", str(zip_path)], stdout=subprocess.PIPE)
    con = duckdb.connect()
    con.execute("set memory_limit='3GB'")
    # DuckDB reads the CSV from the pipe; every value stays text, as published.
    con.execute(
        f"copy (select {select} from read_csv('/dev/fd/{unzip.stdout.fileno()}', "
        f"all_varchar=true, header=true, max_line_size=10000000)) "
        f"to '{out}' (format parquet, compression zstd)"
    )
    unzip.wait()


def download(raw_dir: Path, parquet_dir: Path) -> str:
    """Fetch the latest full files, convert them and delete each zip once converted."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    parquet_dir.mkdir(parents=True, exist_ok=True)
    publish = latest_publish()
    for table, meta in publish["files"].items():
        zip_path = raw_dir / Path(meta["url"]).name
        with requests.get(meta["url"], stream=True, timeout=600) as resp:
            resp.raise_for_status()
            with open(zip_path, "wb") as fh:
                for chunk in resp.iter_content(1 << 20):
                    fh.write(chunk)
        to_parquet(zip_path, table, parquet_dir / f"{table}.parquet")
        zip_path.unlink()
    (parquet_dir / "PUBLISH_DATE").write_text(publish["publish_date"])
    return publish["publish_date"]


def connect(parquet_dir: Path) -> duckdb.DuckDBPyConnection:
    """A DuckDB connection with the three tables the controls query."""
    con = duckdb.connect()
    for table in COLUMNS:
        con.execute(
            f"create or replace view {table} as select * from read_parquet('{parquet_dir / table}.parquet')"
        )
    return con
