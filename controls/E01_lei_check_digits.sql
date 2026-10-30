/*---
id: E01
name: Every LEI is well formed and passes its ISO 17442 check digits
dimension: validity
severity: critical
owner: Entity Reference Data
description: >
  An LEI is 18 letters or digits followed by two check digits. Read as a number,
  with A=10 to Z=35, it must leave remainder 1 when divided by 97 (ISO 7064 MOD
  97-10). Every record in the golden copy is checked, whatever its status.
impact: >
  An identifier that fails its check digits cannot be told apart from a typing
  error, so every system that stores it may be holding the wrong entity's key.
runbook:
  - Look up the record's registration status; an annulled or duplicate record may already have been withdrawn for this reason.
  - If the record is issued, raise it with the managing LOU, which must correct or annul it.
  - Search downstream systems for the identifier and for its nearest valid neighbours, to find where it was keyed in.
---*/
with digits as (
    select
        lei,
        registration_status,
        regexp_full_match(lei, '[0-9A-Z]{18}[0-9]{2}') as well_formed,
        -- Fold the LEI into its remainder mod 97 one character at a time; letters count as two digits.
        list_reduce(
            list_transform(
                string_split(lei, ''),
                lambda ch: case when ch between '0' and '9' then ch else cast(ascii(ch) - 55 as varchar) end
            ),
            lambda acc, d: cast(
                (cast(acc as bigint) * (case when length(d) = 2 then 100 else 10 end) + cast(d as bigint)) % 97
                as varchar
            ),
            '0'
        ) as remainder
    from entities
)

select
    lei,
    cast(null as varchar) as related_lei,
    not (well_formed and remainder = '1') as is_exception,
    case
        when not well_formed then 'not 18 characters plus 2 check digits'
        else 'remainder ' || remainder || ' (must be 1); registration status ' || registration_status
    end as detail
from digits
