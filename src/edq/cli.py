"""edq download | run"""

from __future__ import annotations

import argparse
from pathlib import Path

from edq.controls import load_controls, run_all
from edq.load import connect, download
from edq.report import render_site

ROOT = Path.cwd()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="edq", description=__doc__)
    parser.add_argument("command", choices=["download", "run"])
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "parquet")
    parser.add_argument("--site", type=Path, default=ROOT / "site")
    args = parser.parse_args(argv)

    if args.command == "download":
        print("golden copy", download(ROOT / "data" / "raw", args.data))
        return

    con = connect(args.data)
    con.execute("set memory_limit='3GB'")
    controls = load_controls(ROOT / "controls")
    results = run_all(con, controls)
    for r in results:
        print(
            f"{r.control.id} {r.control.severity:8} {r.checked:>10,} checked {r.exceptions:>10,} exceptions"
        )
    stamp = args.data / "PUBLISH_DATE"
    publish_date = stamp.read_text() if stamp.exists() else "unknown"
    print("wrote", render_site(con, results, publish_date, args.site))


if __name__ == "__main__":
    main()
