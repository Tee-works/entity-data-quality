/*---
id: E07
name: An issued entity's active parent relationship points to a live parent
dimension: timeliness
severity: medium
owner: Entity Relationship Data
description: >
  For issued entities, each active direct or ultimate accounting relationship must
  point to a parent whose LEI is not retired or annulled and whose entity status is
  not inactive. A retired parent usually means the parent merged or was dissolved
  after the relationship was last updated.
impact: >
  The child is rolled up to a group that no longer exists, so exposure and
  ownership views show a dead entity as the top of a live business.
runbook:
  - Look up the parent's successor LEI, if it has one, and its expiration reason.
  - Ask the child's LOU to repoint the relationship to the successor, or to report the current parent.
---*/
select
    r.child_lei as lei,
    r.parent_lei as related_lei,
    p.registration_status in ('RETIRED', 'ANNULLED') or p.entity_status = 'INACTIVE' as is_exception,
    r.rel_type || ' to a parent that is ' || p.registration_status || ' / ' || coalesce(p.entity_status, '?')
    || coalesce(' (expired: ' || nullif(p.expiration_reason, '') || ')', '')
    || coalesce('; successor ' || nullif(p.successor_lei, ''), '') as detail
from relationships as r
inner join entities as c on r.child_lei = c.lei
inner join entities as p on r.parent_lei = p.lei
where
    r.rel_status = 'ACTIVE'
    and r.rel_type in ('IS_DIRECTLY_CONSOLIDATED_BY', 'IS_ULTIMATELY_CONSOLIDATED_BY')
    and c.registration_status = 'ISSUED'
