/*---
id: E10
name: Every issued entity reports its parents or says why not
dimension: completeness
severity: medium
owner: Entity Relationship Data
description: >
  Since 2017 every LEI must carry, for both its direct and its ultimate accounting
  parent, either a relationship record or a reporting exception explaining its
  absence. Each issued entity is checked for both levels; branches and funds, which
  report other relationship types, are left out.
impact: >
  A silent gap cannot be told apart from an entity that has no parent, so ownership
  coverage looks better than it is.
runbook:
  - Ask the managing LOU to collect the parent data, or the reason for not reporting it, at the next renewal.
---*/
with issued as (
    select lei from entities
    where registration_status = 'ISSUED' and category not in ('BRANCH', 'FUND')
),

levels as (
    select
        i.lei,
        lvl.rel_type,
        lvl.exception_category
    from issued as i
    cross join (
        values
        ('IS_DIRECTLY_CONSOLIDATED_BY', 'DIRECT_ACCOUNTING_CONSOLIDATION_PARENT'),
        ('IS_ULTIMATELY_CONSOLIDATED_BY', 'ULTIMATE_ACCOUNTING_CONSOLIDATION_PARENT')
    ) as lvl (rel_type, exception_category)
),

has_rel as (
    select distinct
        child_lei,
        rel_type
    from relationships
    where rel_status = 'ACTIVE'
),

has_exc as (
    select distinct
        lei,
        category
    from exceptions
)

select
    l.lei,
    cast(null as varchar) as related_lei,
    r.child_lei is null and x.lei is null as is_exception,
    case
        when r.child_lei is null and x.lei is null then 'no ' || l.rel_type || ' relationship and no exception'
        else 'reported'
    end as detail
from levels as l
left join has_rel as r on l.lei = r.child_lei and l.rel_type = r.rel_type
left join has_exc as x on l.lei = x.lei and l.exception_category = x.category
