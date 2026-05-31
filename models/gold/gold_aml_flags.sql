-- GOLD: BSA/AML monitoring marts.
-- Two classic compliance patterns every bank must surface:
--
--   1. CTR-reportable: any single cash/wire transaction OVER $10,000 triggers
--      a Currency Transaction Report under the Bank Secrecy Act.
--
--   2. Structuring ("smurfing"): multiple sub-$10,000 cash deposits by the same
--      account on the same day that AGGREGATE over $10,000 -- a deliberate
--      attempt to evade the CTR threshold, itself a reportable red flag.
--
-- This is the kind of domain logic a generic data engineer wouldn't think to
-- build, and it's the heart of what makes this a *banking* pipeline.

with txns as (
    select * from {{ ref('silver_transactions') }}
),

-- 1. single large transactions over the CTR threshold
ctr_reportable as (
    select
        txn_id,
        account_id,
        txn_date,
        amount,
        'CTR_OVER_10K'                       as flag_type,
        'Single transaction exceeds $10,000 CTR threshold' as flag_reason
    from txns
    where amount > 10000
      and txn_code in ('CR', 'WIRE', 'ACH')   -- cash/value-movement codes
),

-- 2. same-day, same-account credit clusters that aggregate over the threshold
daily_credit as (
    select
        account_id,
        txn_date,
        count(*)        as txn_count,
        sum(amount)     as total_amount,
        max(amount)     as largest_single
    from txns
    where flow_direction = 'CREDIT'
    group by account_id, txn_date
),

structuring as (
    select
        cast(account_id || '-' || cast(txn_date as varchar) as varchar) as txn_id,
        account_id,
        txn_date,
        total_amount                          as amount,
        'STRUCTURING_SUSPECT'                 as flag_type,
        'Multiple sub-$10k same-day credits aggregating over threshold (' ||
            cast(txn_count as varchar) || ' txns)' as flag_reason
    from daily_credit
    where largest_single < 10000      -- each individually under the radar
      and total_amount    > 10000     -- but together they clear it
      and txn_count       >= 3
)

select * from ctr_reportable
union all
select * from structuring
