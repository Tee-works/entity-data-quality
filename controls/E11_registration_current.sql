/*---
id: E11
name: Registrations are renewed on time
dimension: timeliness
severity: low
owner: Entity Reference Data
description: >
  An LEI must be renewed every year, when its LOU re-validates the reference data
  against the business registry. Among LEIs that are issued or lapsed, a lapsed LEI
  is an exception: its data has not been confirmed since its renewal date. Issued
  LEIs whose renewal date is before the golden copy's own date are flagged too.
impact: >
  Lapsed data still identifies the entity, but its name, address and parents may be
  out of date, and regulators expect counterparties to keep their LEI current.
runbook:
  - Rank lapsed LEIs by how much the business depends on them (open trades, active clients).
  - Ask the entity, or the LOU, to renew; for counterparties, renewal can be a condition of trading.
---*/
-- The golden copy's own date: the latest update it contains.
with as_of as (
    select max(try_cast(left(last_update, 10) as date)) as as_of_date from entities
)

select
    e.lei,
    cast(null as varchar) as related_lei,
    e.registration_status = 'LAPSED'
    or try_cast(left(e.next_renewal, 10) as date) < a.as_of_date as is_exception,
    e.registration_status || ', next renewal ' || left(e.next_renewal, 10)
    || ', managed by ' || e.managing_lou as detail
from entities as e
cross join as_of as a
where e.registration_status in ('ISSUED', 'LAPSED')
