-- SILVER: branches cleaned & standardized.
--   * blank fdic_cert flagged (a data-quality issue that matters for
--     deposit-insurance reporting)

with src as (
    select * from {{ ref('bronze_branches') }}
)

select
    branch_id,
    trim(branch_name)                                          as branch_name,
    upper(trim(state))                                         as state,
    nullif(trim(cast(fdic_cert as varchar)), '')               as fdic_cert,
    case when nullif(trim(cast(fdic_cert as varchar)), '') is null
         then true else false end                              as missing_fdic_cert
from src
