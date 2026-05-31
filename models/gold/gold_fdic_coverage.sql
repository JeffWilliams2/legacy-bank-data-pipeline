-- GOLD: FDIC deposit-insurance coverage by customer.
-- FDIC insures deposits up to $250,000 per depositor, per institution, per
-- ownership category. This mart aggregates each customer's INSURED-DEPOSIT
-- accounts (excluding lines of credit) and flags uninsured exposure -- a
-- figure risk and treasury teams watch closely.

with accounts as (
    select * from {{ ref('silver_accounts') }}
    where is_insured_deposit = true
      and status = 'OPEN'
),

customers as (
    select * from {{ ref('silver_customers') }}
),

by_customer as (
    select
        customer_id,
        count(*)                                  as deposit_account_count,
        sum(current_balance)                      as total_deposits
    from accounts
    group by customer_id
)

select
    c.customer_id,
    cust.full_name,
    cust.risk_rating,
    c.deposit_account_count,
    c.total_deposits,
    least(c.total_deposits, 250000)               as fdic_insured_amount,
    greatest(c.total_deposits - 250000, 0)        as uninsured_exposure,
    case when c.total_deposits > 250000
         then true else false end                 as exceeds_fdic_limit
from by_customer c
left join customers cust using (customer_id)
order by uninsured_exposure desc
