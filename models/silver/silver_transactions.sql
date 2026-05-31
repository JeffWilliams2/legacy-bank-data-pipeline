-- SILVER: transactions cleaned & standardized.
-- The core business rule of this layer: the source stores every amount as a
-- POSITIVE number, with the debit/credit nature implied by txn_code. Analysts
-- can't sum that. Here we derive signed_amount so debits are negative and
-- credits positive -- now balances and net-flow aggregate correctly.

with src as (
    select * from {{ ref('bronze_transactions') }}
)

select
    txn_id,
    account_id,
    {{ parse_legacy_date('txn_date') }}        as txn_date,
    txn_code,
    channel,
    {{ clean_money('amount') }}                as amount,           -- always positive (as received)
    case
        when txn_code in ('DR', 'ATM', 'FEE', 'WIRE')
            then -1 * {{ clean_money('amount') }}                   -- money out
        else {{ clean_money('amount') }}                           -- money in
    end                                        as signed_amount,
    case when txn_code in ('DR', 'ATM', 'FEE', 'WIRE')
         then 'DEBIT' else 'CREDIT' end        as flow_direction
from src
