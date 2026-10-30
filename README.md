# Entity data quality

Eleven SQL data quality controls on the [GLEIF golden copy](https://www.gleif.org/en/lei-data/gleif-golden-copy): every legal entity identifier (LEI) in the world, the parent relationships between them, and the exceptions entities give for not reporting a parent.

**Read the write-up:** https://tee-works.github.io/entity-data-quality/

## What the controls found (golden copy of 30 October 2026)

3,478,835 entities and 492,253 relationships were checked in about ten seconds on a laptop.

- **The identifiers are clean.** All 256 LEIs that fail their ISO 17442 check digits (E01) are already annulled or marked duplicate. The register has caught its own typing errors.
- **The ownership links are where it breaks.** In 1,477 cases a subsidiary names an ultimate parent that the top of its own direct-parent chain contradicts (E06). The top says it has no parent at all, or names a different one. In 748 of them the top's record is current, not lapsed.
  - RSA Insurance Group was bought by Intact Financial in 2021. Its subsidiaries name Intact as their ultimate parent, but RSA's own record, updated 26 October 2026, still reports no known parent.
- **Ultimate parents that are not at the top.** 307 subsidiaries name an "ultimate" parent that reports a parent of its own (E05). Examples are JLT Group under Marsh & McLennan, and NIBC Bank under ABN AMRO.
- **Rare structural faults.**
  - Two pairs of companies name each other as direct parent, which is a loop (E04).
  - Five relationships name the entity as its own parent (E03).
  - 23 pairs of issued LEIs share the same registry, registry ID and legal name (E09).
  - Four parent LEIs are not in the register at all (E02).
- **Stale data.** 38% of issued or lapsed LEIs have not been renewed (E11). This is well known and mostly harmless for dormant entities, but it matters for counterparties still being traded with.

A finding means two records disagree, not which one is wrong. Settling that takes the companies' own filings and the local operating unit (LOU) that manages each record.

## The controls

| | Control | Dimension | Severity |
|---|---|---|---|
| E01 | Every LEI is well formed and passes its ISO 17442 check digits | validity | critical |
| E02 | Every accounting parent named by LEI exists in the register | completeness | high |
| E03 | No entity is its own accounting parent | validity | high |
| E04 | Following direct parents never comes back to the same entity | consistency | critical |
| E05 | An ultimate parent has no accounting parent of its own | consistency | high |
| E06 | The ultimate parent agrees with the top of the direct-parent chain | consistency | high |
| E07 | An issued entity's active parent relationship points to a live parent | timeliness | medium |
| E08 | A successor LEI points to a record that can still be used | accuracy | medium |
| E09 | One issued LEI per registered legal entity | uniqueness | high |
| E10 | Every issued entity reports its parents or says why not | completeness | medium |
| E11 | Registrations are renewed on time | timeliness | low |

Each control is one SQL file in `controls/`. A YAML header gives its owner, severity, what a failure costs, and a triage runbook. The query returns one row per item checked (`lei, related_lei, is_exception, detail`), so every exception rate has a denominator. Adding a control means adding a file.

## How it works

- `edq download` fetches the latest full files from GLEIF's API. They are about 570 MB zipped and about 5 GB as CSV. Each zip is streamed straight into Parquet with only the columns used, so the CSV never touches the disk. The result is about 260 MB.
- `edq run` runs every control in DuckDB, then writes the page and `results.csv` to `site/`.
- The tests build a small synthetic register with one planted defect per control. They check that every control finds its own defect and nothing else.
- CI runs ruff, sqlfluff and the tests on every push. A weekly workflow refreshes the data and republishes the page.

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/edq download   # about 570 MB from goldencopy.gleif.org
.venv/bin/edq run
.venv/bin/pytest -q
```

## Related

This is the same approach as [holdings data quality](https://github.com/Tee-works/holdings-data-quality): SQL controls on a large asset manager's public SEC filings. One of those controls found a subsidiary counted twice inside its parent for four quarters.

Independent work on public data. Not affiliated with or endorsed by GLEIF or any entity named.
