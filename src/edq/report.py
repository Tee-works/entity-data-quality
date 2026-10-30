"""Turn control results into the published note and the results files.

Everything shown is computed here from the golden copy, so the page can be
regenerated from any publish and every number traced back to a query.
"""

from __future__ import annotations

import csv
import html
from pathlib import Path

import duckdb
from jinja2 import Environment, FileSystemLoader, select_autoescape

from edq.controls import Control, Result

TEMPLATES = Path(__file__).resolve().parents[2] / "templates"


def _names(con: duckdb.DuckDBPyConnection, leis: list[str]) -> dict[str, dict]:
    if not leis:
        return {}
    rows = con.execute(
        "select lei, legal_name, jurisdiction, registration_status, left(last_update, 10) "
        "from entities where lei in (select unnest(?))",
        [leis],
    ).fetchall()
    return {
        r[0]: {"name": r[1], "jurisdiction": r[2], "status": r[3], "updated": r[4]} for r in rows
    }


def contradicted_groups(con, control: Control, limit: int = 8) -> dict:
    """E06 grouped by stated ultimate parent: where a group's own records disagree."""
    con.execute(
        f"create or replace temp table _e06 as select * from ({control.query}) where is_exception"
    )
    con.execute(
        "create or replace temp table _e06g as select related_lei as ultimate, "
        "regexp_extract(detail, 'chain top (\\w+)', 1) as top, "
        "regexp_extract(detail, '\\((\\w+)\\) (reports|states)', 1) as top_status, "
        "coalesce(nullif(regexp_extract(detail, 'reports (\\w+)', 1), ''), 'a different ultimate parent') as top_says, "
        "count(*) as children from _e06 group by all"
    )
    rows = con.execute(
        f"select ultimate, top, top_status, top_says, children from _e06g order by children desc, ultimate limit {limit}"
    ).fetchall()
    names = _names(con, [r[0] for r in rows] + [r[1] for r in rows])
    by_status = dict(
        con.execute("select top_status, sum(children) from _e06g group by 1").fetchall()
    )
    tops_issued = con.execute(
        "select count(distinct top) from _e06g where top_status = 'ISSUED'"
    ).fetchone()[0]
    return {
        "rows": [
            {
                "ultimate": names.get(r[0], {}),
                "top": names.get(r[1], {}),
                "top_lei": r[1],
                "top_status": r[2],
                "top_says": r[3].replace("_", " ").lower(),
                "children": r[4],
            }
            for r in rows
        ],
        "issued_children": int(by_status.get("ISSUED", 0)),
        "lapsed_children": int(by_status.get("LAPSED", 0)),
        "tops_issued": tops_issued,
    }


def not_top_examples(con, control: Control, limit: int = 6) -> list[dict]:
    """E05: named ultimate parents that report a parent of their own."""
    rows = con.execute(
        f"select related_lei, regexp_extract(detail, 'direct parent (\\w+)', 1), count(*) "
        f"from ({control.query}) where is_exception group by 1, 2 order by 3 desc, 1 limit {limit}"
    ).fetchall()
    names = _names(con, [r[0] for r in rows] + [r[1] for r in rows])
    return [
        {"named": names.get(r[0], {}), "its_parent": names.get(r[1], {}), "children": r[2]}
        for r in rows
    ]


def exception_rows(con, control: Control) -> list[dict]:
    rows = con.execute(
        f"select lei, related_lei, detail from ({control.query}) where is_exception order by lei"
    ).fetchall()
    names = _names(con, [r[0] for r in rows] + [r[1] for r in rows if r[1]])
    return [
        {
            "lei": r[0],
            "entity": names.get(r[0], {}),
            "related": r[1],
            "other": names.get(r[1], {}),
            "detail": r[2],
        }
        for r in rows
    ]


def write_results(results: list[Result], out: Path) -> None:
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            ["id", "name", "dimension", "severity", "owner", "checked", "exceptions", "rate"]
        )
        for r in results:
            c = r.control
            w.writerow(
                [
                    c.id,
                    c.name,
                    c.dimension,
                    c.severity,
                    c.owner,
                    r.checked,
                    r.exceptions,
                    f"{r.rate:.6f}",
                ]
            )


def render_site(con, results: list[Result], publish_date: str, out_dir: Path) -> Path:
    by_id = {r.control.id: r for r in results}
    entities = con.execute("select count(*) from entities").fetchone()[0]
    relationships = con.execute("select count(*) from relationships").fetchone()[0]
    case = {
        "entities": entities,
        "relationships": relationships,
        "e06": contradicted_groups(con, by_id["E06"].control),
        "e05": not_top_examples(con, by_id["E05"].control),
        "loops": exception_rows(con, by_id["E04"].control),
        "dupes": [r for r in exception_rows(con, by_id["E09"].control) if r["related"]],
        "self": exception_rows(con, by_id["E03"].control),
        "e06_sql": html.escape(by_id["E06"].control.sql),
    }
    env = Environment(
        loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html", "j2"])
    )
    env.filters["n"] = lambda v: f"{v:,}"
    page = env.get_template("index.html.j2").render(
        results=results, by_id=by_id, case=case, publish_date=publish_date[:10]
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(page)
    write_results(results, out_dir / "results.csv")
    return out_dir / "index.html"
