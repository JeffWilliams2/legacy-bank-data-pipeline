-- GOLD: executive summary -- portfolio rollup by branch and account type.
-- The single mart an exec opens first: deposits, account counts, and net flow
-- sliced by branch and product.

with accounts as (
    select * from {{ ref('silver_accounts') }}
    where status = 'OPEN'
),

branches as (
    select * from {{ ref('silver_branches') }}
),

txns as (
    select * from {{ ref('silver_transactions') }}
),

net_flow as (
    select
        a.branch_id,
        a.account_type,
        sum(t.signed_amount) as net_flow
    from accounts a
    left join txns t on a.account_id = t.account_id
    group by a.branch_id, a.account_type
)

select
    b.branch_id,
    b.branch_name,
    b.state,
    a.account_type,
    count(distinct a.account_id)          as account_count,
    sum(a.current_balance)                as total_balance,
    avg(a.current_balance)                as avg_balance,
    coalesce(nf.net_flow, 0)              as net_transaction_flow
from accounts a
left join branches b   using (branch_id)
left join net_flow nf  on a.branch_id = nf.branch_id and a.account_type = nf.account_type
group by b.branch_id, b.branch_name, b.state, a.account_type, nf.net_flow
order by total_balance desc
