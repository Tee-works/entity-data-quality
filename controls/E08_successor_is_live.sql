/*---
id: E08
name: A successor LEI points to a record that can still be used
dimension: accuracy
severity: medium
owner: Entity Reference Data
description: >
  Where a record names a successor entity (after a merger, for example), the
  successor LEI must exist in the register and must not itself be annulled or a
  duplicate. A retired successor passes only if it in turn names a successor of
  its own, so the chain still leads somewhere.
impact: >
  Following a merged entity to its successor is how systems keep positions and
  contracts attached to a live counterparty; a dead end loses them.
runbook:
  - Check whether the successor was annulled as a duplicate of another LEI, and point to that one.
  - If the successor itself merged, ask its LOU to record its own successor.
---*/
select
    e.lei,
    e.successor_lei as related_lei,
    s.lei is null
    or s.registration_status in ('ANNULLED', 'DUPLICATE')
    or (s.registration_status = 'RETIRED' and coalesce(s.successor_lei, '') = '') as is_exception,
    case
        when s.lei is null then 'successor ' || e.successor_lei || ' is not in the register'
        else
            'successor is ' || s.registration_status
            || case
                when s.registration_status = 'RETIRED' and coalesce(s.successor_lei, '') = ''
                    then ' with no successor of its own'
                else ''
            end
    end as detail
from entities as e
left join entities as s on e.successor_lei = s.lei
where coalesce(e.successor_lei, '') <> ''
