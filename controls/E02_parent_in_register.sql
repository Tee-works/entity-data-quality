/*---
id: E02
name: Every accounting parent named by LEI exists in the register
dimension: completeness
severity: high
owner: Entity Relationship Data
description: >
  For each active direct or ultimate accounting-consolidation relationship whose
  parent is identified by an LEI, that LEI must be a record in the same golden copy.
impact: >
  A parent that is not in the register breaks the hierarchy at that point: rolling
  exposures up to the group, or screening the group, silently stops at the child.
runbook:
  - Check the parent LEI for typing errors against LEIs with a similar name in the same jurisdiction.
  - If the parent was never registered, ask the child's LOU to report a NO_LEI exception instead.
---*/
select
    r.child_lei as lei,
    r.parent_lei as related_lei,
    e.lei is null as is_exception,
    r.rel_type || ' points to ' || r.parent_lei
    || case when e.lei is null then ', which is not in the register' else '' end as detail
from relationships as r
left join entities as e on r.parent_lei = e.lei
where
    r.parent_id_type = 'LEI'
    and r.rel_status = 'ACTIVE'
    and r.rel_type in ('IS_DIRECTLY_CONSOLIDATED_BY', 'IS_ULTIMATELY_CONSOLIDATED_BY')
