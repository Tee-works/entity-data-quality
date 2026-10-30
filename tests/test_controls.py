"""Each control finds the defect planted for it in a small synthetic register, and nothing else."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import pytest

from edq.controls import COLUMNS, load_controls, parse_control, run_control
from edq.load import COLUMNS as TABLE_COLUMNS
from edq.load import connect

ROOT = Path(__file__).resolve().parents[1]


def lei(stem: str) -> str:
    """A valid LEI from an 18-character stem (ISO 7064 MOD 97-10 check digits)."""
    stem = stem.upper().ljust(18, "0")[:18]
    digits = "".join(str(int(ch, 36)) for ch in stem) + "00"
    return stem + f"{98 - int(digits) % 97:02d}"


# Named entities for readability; every LEI is valid unless planted otherwise.
L = {
    k: lei(f"TEST{k}")
    for k in [
        "PARENT",
        "CHILD",
        "GRAND",
        "TOPNOPAR",
        "SUB1",
        "SUBTOP",
        "LOOPA",
        "LOOPB",
        "SELF",
        "ORPHAN",
        "DEADPAR",
        "DEADKID",
        "MERGED",
        "DEADSUCC",
        "DUP1",
        "DUP2",
        "SILENT",
        "LAPSED",
        "ULTNOTTOP",
        "ULTPAR",
        "ULTKID",
    ]
}
BAD_CHECK = L["PARENT"][:18] + ("00" if L["PARENT"][18:] != "00" else "01")
MISSING = lei("NOTINREGISTER")


def entity(code, **kw):
    row = dict.fromkeys(TABLE_COLUMNS["entities"].values())
    row.update(
        lei=L.get(code, code),
        legal_name=f"{code} Ltd",
        jurisdiction="GB",
        category="GENERAL",
        entity_status="ACTIVE",
        registration_status="ISSUED",
        ra_id="RA000585",
        ra_entity_id=f"ID-{code}",
        next_renewal="2027-06-01T00:00:00Z",
        last_update="2026-10-01T00:00:00Z",
        managing_lou="LOU1",
    )
    row.update(kw)
    return row


def rel(child, parent, kind="IS_DIRECTLY_CONSOLIDATED_BY"):
    row = dict.fromkeys(TABLE_COLUMNS["relationships"].values())
    row.update(
        child_lei=L.get(child, child),
        parent_lei=L.get(parent, parent),
        parent_id_type="LEI",
        rel_type=kind,
        rel_status="ACTIVE",
    )
    return row


def exc(code, level, reason):
    category = f"{level}_ACCOUNTING_CONSOLIDATION_PARENT"
    return {"lei": L[code], "category": category, "reason": reason}


@pytest.fixture(scope="session")
def con(tmp_path_factory) -> duckdb.DuckDBPyConnection:
    d = tmp_path_factory.mktemp("register")
    entities = [entity(k) for k in L if k not in ("DUP2",)]
    entities += [
        entity(
            "DUP2", legal_name="DUP1 Ltd", ra_entity_id="ID-DUP1"
        ),  # E09: same registry, id, name
        entity(BAD_CHECK, registration_status="ANNULLED"),  # E01
    ]
    for e in entities:
        if e["lei"] == L["DEADPAR"]:
            e.update(registration_status="RETIRED", entity_status="INACTIVE")  # E07
        if e["lei"] == L["MERGED"]:
            e.update(registration_status="RETIRED", successor_lei=L["DEADSUCC"])
        if e["lei"] == L["DEADSUCC"]:
            e.update(registration_status="RETIRED")  # E08: dead end
        if e["lei"] == L["LAPSED"]:
            e.update(registration_status="LAPSED")  # E11

    relationships = [
        # A clean group: CHILD -> PARENT -> GRAND, ultimate GRAND for both.
        rel("CHILD", "PARENT"),
        rel("PARENT", "GRAND"),
        rel("CHILD", "GRAND", "IS_ULTIMATELY_CONSOLIDATED_BY"),
        rel("PARENT", "GRAND", "IS_ULTIMATELY_CONSOLIDATED_BY"),
        # E06: SUB1's chain tops at SUBTOP, which says it has no parent; SUB1 claims GRAND.
        rel("SUB1", "SUBTOP"),
        rel("SUB1", "GRAND", "IS_ULTIMATELY_CONSOLIDATED_BY"),
        # E05: ULTKID names ULTNOTTOP as ultimate, but ULTNOTTOP has its own parent.
        rel("ULTKID", "ULTNOTTOP"),
        rel("ULTKID", "ULTNOTTOP", "IS_ULTIMATELY_CONSOLIDATED_BY"),
        rel("ULTNOTTOP", "ULTPAR"),
        rel("LOOPA", "LOOPB"),
        rel("LOOPB", "LOOPA"),  # E04
        rel("SELF", "SELF"),  # E03
        rel("ORPHAN", MISSING, "IS_ULTIMATELY_CONSOLIDATED_BY"),  # E02
        rel("DEADKID", "DEADPAR"),  # E07
    ]
    exceptions = [exc("SUBTOP", "DIRECT", "NON_CONSOLIDATING")]
    # Everyone else reports at least an exception at both levels, except SILENT (E10).
    reported = {r["child_lei"] for r in relationships}
    for code in L:
        if code != "SILENT" and L[code] not in reported:
            exceptions += [
                exc(code, "DIRECT", "NATURAL_PERSONS"),
                exc(code, "ULTIMATE", "NATURAL_PERSONS"),
            ]
    for code in ["ULTNOTTOP", "LOOPA", "LOOPB", "SELF", "DEADKID"]:
        exceptions.append(exc(code, "ULTIMATE", "NO_LEI"))
    exceptions.append(exc("ORPHAN", "DIRECT", "NO_LEI"))

    for name, rows in [
        ("entities", entities),
        ("relationships", relationships),
        ("exceptions", exceptions),
    ]:
        frame = pd.DataFrame(rows, columns=list(TABLE_COLUMNS[name].values())).astype("string")
        duckdb.from_df(frame).write_parquet(str(d / f"{name}.parquet"))
    return connect(d)


CONTROLS = {c.id: c for c in load_controls(ROOT / "controls")}
PLANTED = {
    "E01": {BAD_CHECK},
    "E02": {L["ORPHAN"]},
    "E03": {L["SELF"]},
    "E04": {L["LOOPA"], L["LOOPB"]},
    "E05": {L["ULTKID"]},
    "E06": {L["SUB1"]},
    "E07": {L["DEADKID"]},
    "E08": {L["MERGED"]},
    "E09": {L["DUP1"], L["DUP2"]},
    "E10": {L["SILENT"]},
    "E11": {L["LAPSED"]},
}


def test_every_control_has_a_planted_defect():
    assert set(CONTROLS) == set(PLANTED)


@pytest.mark.parametrize("cid", sorted(PLANTED))
def test_control_finds_only_its_defect(con, cid):
    result = run_control(con, CONTROLS[cid])
    found = set(
        con.execute(
            f"select distinct lei from ({CONTROLS[cid].query}) where is_exception"
        ).fetchnumpy()["lei"]
    )
    assert found == PLANTED[cid]
    assert result.exceptions >= len(PLANTED[cid])


def test_check_digit_helper_matches_a_real_lei():
    assert lei("5493001KJTIIGC8Y1R") == "5493001KJTIIGC8Y1R12"


def test_header_is_required(tmp_path):
    bad = tmp_path / "E99_bad.sql"
    bad.write_text("select 1")
    with pytest.raises(ValueError, match="header"):
        parse_control(bad)


def test_output_columns_are_enforced(con, tmp_path):
    path = tmp_path / "E98_wrong.sql"
    path.write_text(
        "/*---\nid: E98\nname: x\ndimension: validity\nseverity: low\nowner: x\n"
        "description: x\nimpact: x\nrunbook: [x]\n---*/\nselect lei from entities"
    )
    with pytest.raises(ValueError, match=str(COLUMNS[0])):
        run_control(con, parse_control(path))
