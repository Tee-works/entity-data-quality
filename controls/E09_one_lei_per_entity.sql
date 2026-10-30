/*---
id: E09
name: One issued LEI per registered legal entity
dimension: uniqueness
severity: high
owner: Entity Reference Data
description: >
  Issued LEIs for general entities are grouped by business registry and registry
  ID. A group is an exception when two or more issued LEIs share the same registry,
  registry ID and legal name (compared ignoring case and spacing), which is one
  legal entity registered twice. Groups where the names differ are reported for
  review, not as exceptions: that pattern is usually a registry ID entered wrongly.
  Placeholder registry codes (RA999999) are left out.
impact: >
  Two identifiers for one entity split its exposures, filings and relationships in
  two, and any count of entities is overstated.
runbook:
  - Confirm with the registry that both LEIs describe the same legal entity.
  - Ask the LOU that issued the later LEI to mark it DUPLICATE, pointing at the earlier one.
  - Move any relationships from the duplicate to the surviving LEI.
---*/
with issued as (
    select
        lei,
        ra_id,
        ra_entity_id,
        legal_name,
        regexp_replace(upper(trim(legal_name)), '\s+', ' ', 'g') as name_key
    from entities
    where
        registration_status = 'ISSUED'
        and category = 'GENERAL'
        and coalesce(ra_entity_id, '') <> ''
        and ra_id not like 'RA999999%'
),

grouped as (
    select
        lei,
        ra_id,
        ra_entity_id,
        legal_name,
        count(*) over (partition by ra_id, ra_entity_id, name_key) as same_name,
        min(lei) over (partition by ra_id, ra_entity_id, name_key) as first_lei
    from issued
)

select
    lei,
    case when same_name > 1 and lei <> first_lei then first_lei end as related_lei,
    same_name > 1 as is_exception,
    case
        when same_name > 1
            then same_name || ' issued LEIs for ' || legal_name || ' at ' || ra_id || ' / ' || ra_entity_id
        else 'unique'
    end as detail
from grouped
