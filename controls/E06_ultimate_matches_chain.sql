/*---
id: E06
name: The ultimate parent agrees with the top of the direct-parent chain
dimension: consistency
severity: high
owner: Entity Relationship Data
description: >
  For each entity with an active direct parent and an active ultimate parent, the
  direct-parent links are followed to the top of the chain. The child's stated
  ultimate parent is contradicted when the entity at the top says something
  incompatible about itself: it names a different ultimate parent, or it reports
  that it has no parent entity at all (NON_CONSOLIDATING, NATURAL_PERSONS or
  NO_KNOWN_PERSON). Tops that report a parent without an LEI (NO_LEI) or keep it
  private (NON_PUBLIC) are consistent and pass; an ultimate parent found part-way
  up the chain is left to E05.
impact: >
  Two records in the same register disagree about who owns the group, so which
  answer a user gets depends on which entity they start from.
runbook:
  - Read the chain in the detail and the top entity's own exception or ultimate parent.
  - Decide with the LOUs involved which record is out of date; usually the top's exception predates an acquisition.
  - Correct the stale record, then re-run E05 and E06 for the whole group.
---*/
with recursive direct_parent as (
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
),

ultimate as (
    select
        child_lei,
        any_value(parent_lei) as parent_lei
    from relationships
    where rel_type = 'IS_ULTIMATELY_CONSOLIDATED_BY' and rel_status = 'ACTIVE' and parent_id_type = 'LEI'
    group by child_lei
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

chain_top as (
    select
        start_lei,
        arg_max(node, depth) as top_lei,
        arg_max(path, depth) as path
    from walk
    group by start_lei
),

top_says as (
    select
        lei,
        string_agg(distinct reason, ', ') as no_parent_reason
    from exceptions
    where
        category = 'DIRECT_ACCOUNTING_CONSOLIDATION_PARENT'
        and reason in ('NON_CONSOLIDATING', 'NATURAL_PERSONS', 'NO_KNOWN_PERSON')
    group by lei
),

checked as (
    select
        t.start_lei,
        u.parent_lei as stated_ultimate,
        t.top_lei,
        t.path,
        tu.parent_lei as top_ultimate,
        ts.no_parent_reason,
        te.registration_status as top_status,
        u.parent_lei <> t.top_lei
        and not list_contains(t.path, u.parent_lei)
        and (
            (tu.parent_lei is not null and tu.parent_lei <> u.parent_lei)
            or (tu.parent_lei is null and ts.no_parent_reason is not null)
        ) as is_exception
    from chain_top as t
    inner join ultimate as u on t.start_lei = u.child_lei
    left join ultimate as tu on t.top_lei = tu.child_lei
    left join top_says as ts on t.top_lei = ts.lei
    left join entities as te on t.top_lei = te.lei
)

select
    start_lei as lei,
    stated_ultimate as related_lei,
    is_exception,
    case
        when not is_exception then 'consistent with the top of the chain'
        when top_ultimate is not null
            then
                'states ultimate ' || stated_ultimate || '; chain top ' || top_lei || ' (' || top_status
                || ') states ultimate ' || top_ultimate
        else
            'states ultimate ' || stated_ultimate || '; chain top ' || top_lei || ' (' || top_status
            || ') reports ' || no_parent_reason
    end || ' | chain: ' || array_to_string(path, ' > ') as detail
from checked
