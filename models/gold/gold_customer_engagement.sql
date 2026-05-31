-- GOLD: customer engagement scoring.
-- A simple, explainable engagement score from transaction recency, frequency,
-- and product holdings -- the kind of mart that feeds retention dashboards.

with txns as (
    select * from {{ ref('silver_transactions') }}
),

accounts as (
    select * from {{ ref('silver_accounts') }}
),

customers as (
    select * from {{ ref('silver_customers') }}
),

acct_activity as (
    select
        a.customer_id,
        count(distinct a.account_id)                         as account_count,
        count(t.txn_id)                                      as txn_count,
        max(t.txn_date)                                      as last_txn_date,
        date_diff('day', max(t.txn_date), current_date)      as days_since_last_txn
    from accounts a
    left join txns t on a.account_id = t.account_id
    group by a.customer_id
)

select
    cust.customer_id,
    cust.full_name,
    cust.age_years,
    aa.account_count,
    aa.txn_count,
    aa.last_txn_date,
    aa.days_since_last_txn,
    -- transparent 0-100 score: recency (50) + frequency (30) + breadth (20)
    least(100,
        (case when aa.days_since_last_txn <= 30  then 50
              when aa.days_since_last_txn <= 90  then 35
              when aa.days_since_last_txn <= 180 then 20
              else 5 end)
      + least(30, aa.txn_count / 5)
      + least(20, aa.account_count * 10)
    )                                                        as engagement_score,
    case
        when aa.days_since_last_txn <= 30  then 'ACTIVE'
        when aa.days_since_last_txn <= 180 then 'PASSIVE'
        else 'AT_RISK'
    end                                                      as engagement_tier
from customers cust
left join acct_activity aa using (customer_id)
order by engagement_score desc
