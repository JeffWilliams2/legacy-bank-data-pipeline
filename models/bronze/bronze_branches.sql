{{
  config(materialized='view')
}}

-- BRONZE: raw landing for branches.
-- No business transforms. We preserve the source exactly as received and
-- stamp audit metadata so we can always prove what arrived and when --
-- non-negotiable in a regulated/audited environment.

select
    *,
    '{{ source('raw', 'raw_branches') }}'  as _source_table,
    current_timestamp                  as _loaded_at,
    '{{ invocation_id }}'              as _batch_id
from {{ source('raw', 'raw_branches') }}
