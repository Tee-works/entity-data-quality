/*---
id: E04
name: Following direct parents never comes back to the same entity
dimension: consistency
severity: critical
owner: Entity Relationship Data
description: >
  Starting from every entity with an active direct parent, the direct-parent links
  are followed upwards (up to 40 steps). An entity is an exception when the walk
  reaches an entity already on its own path, so the hierarchy loops. Self-loops are
  left to E03.
impact: >
  A loop has no top, so there is no ultimate parent to roll up to, and naive
  traversals never finish.
runbook:
  - Read the path in the detail and find the link that contradicts the entities' own filings.
  - Raise the wrong link with the LOU that manages the child on that link.
---*/
with recursive direct_parent as (
    select
        child_lei,
        parent_lei
    from relationships
    where
        rel_type = 'IS_DIRECTLY_CONSOLIDATED_BY'
        and rel_status = 'ACTIVE'
        and parent_id_type = 'LEI'
        and child_lei <> parent_lei
),

walk (start_lei, node, depth, path) as (
    select
        child_lei,
        parent_lei,
        1,
        [child_lei, parent_lei]
    from direct_parent
    union all
    select
        w.start_lei,
        d.parent_lei,
        w.depth + 1,
        list_append(w.path, d.parent_lei)
    from walk as w
    inner join direct_parent as d on w.node = d.child_lei
    where w.depth < 40 and not list_contains(w.path, d.parent_lei)
),

loops as (
    select distinct
        w.start_lei,
        list_append(w.path, d.parent_lei) as loop_path
    from walk as w
    inner join direct_parent as d on w.node = d.child_lei
    where list_contains(w.path, d.parent_lei)
),

first_loop as (
    select
        start_lei,
        any_value(loop_path) as loop_path
    from loops
    group by start_lei
)

select
    d.child_lei as lei,
    d.parent_lei as related_lei,
    l.start_lei is not null as is_exception,
    coalesce('loop: ' || array_to_string(l.loop_path, ' > '), 'direct parent chain terminates') as detail
from direct_parent as d
left join first_loop as l on d.child_lei = l.start_lei
