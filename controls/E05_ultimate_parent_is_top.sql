/*---
id: E05
name: An ultimate parent has no accounting parent of its own
dimension: consistency
severity: high
owner: Entity Relationship Data
description: >
  For each active ultimate-parent relationship, the named ultimate parent must not
  itself report an active direct accounting parent. If it does, it is not the top of
  the group, and the child's ultimate parent should be further up.
impact: >
  Group exposure, sanctions screening and consolidation by ultimate parent all stop
  one level too low, splitting one group into several.
runbook:
  - Follow the ultimate parent's own direct parent to the top of the chain.
  - If the top is consolidated with the child, ask the child's LOU to update the ultimate parent.
  - If the ultimate parent's own direct parent is wrong, raise that relationship instead.
---*/
with ultimate as (
    select
        child_lei,
        parent_lei
    from relationships
    where rel_type = 'IS_ULTIMATELY_CONSOLIDATED_BY' and rel_status = 'ACTIVE' and parent_id_type = 'LEI'
),

direct_parent as (
    select
        child_lei,
        any_value(parent_lei) as parent_lei
    from relationships
    where
        rel_type = 'IS_DIRECTLY_CONSOLIDATED_BY'
        and rel_status = 'ACTIVE'
        and parent_id_type = 'LEI'
        and child_lei <> parent_lei
    group by child_lei
)

select
    u.child_lei as lei,
    u.parent_lei as related_lei,
    up.parent_lei is not null and u.parent_lei <> u.child_lei as is_exception,
    case
        when up.parent_lei is not null
            then 'ultimate parent ' || u.parent_lei || ' reports its own direct parent ' || up.parent_lei
        else 'ultimate parent reports no direct parent'
    end as detail
from ultimate as u
left join direct_parent as up on u.parent_lei = up.child_lei
