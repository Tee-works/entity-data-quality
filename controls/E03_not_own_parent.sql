/*---
id: E03
name: No entity is its own accounting parent
dimension: validity
severity: high
owner: Entity Relationship Data
description: >
  An active direct or ultimate accounting-consolidation relationship must link two
  different entities. (Fund-management and sub-fund relationships are left out:
  a self-managed fund can legitimately name itself.)
impact: >
  A self-loop either hides the real parent or makes a group's top look like a
  subsidiary, and any traversal of the hierarchy has to special-case it.
runbook:
  - Check the entity's own filings for its real parent, if any.
  - If it has none, the relationship should be replaced with a NON_CONSOLIDATING or NATURAL_PERSONS exception.
---*/
select
    child_lei as lei,
    parent_lei as related_lei,
    child_lei = parent_lei as is_exception,
    rel_type || case when child_lei = parent_lei then ' names the entity itself' else '' end as detail
from relationships
where
    rel_status = 'ACTIVE'
    and parent_id_type = 'LEI'
    and rel_type in ('IS_DIRECTLY_CONSOLIDATED_BY', 'IS_ULTIMATELY_CONSOLIDATED_BY')
