-- SILVER: accounts cleaned & standardized.
--   * current_balance stripped of '$'/commas and cast to decimal
--   * open_date parsed from messy formats
--   * legacy acct_type_code decoded to a human label + deposit flag

with src as (
    select * from {{ ref('bronze_accounts') }}
)

select
    account_id,
    customer_id,
    branch_id,
    acct_type_code,
    {{ decode_account_type('acct_type_code') }}   as account_type,
    {{ account_is_deposit('acct_type_code') }}    as is_insured_deposit,
    {{ parse_legacy_date('open_date') }}          as open_date,
    {{ clean_money('current_balance') }}          as current_balance,
    upper(trim(status))                           as status
from src
