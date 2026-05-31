-- SILVER: customers cleaned & standardized.
--   * date_of_birth parsed from 4 messy formats into a real DATE
--   * blank KYC status normalized to 'UNKNOWN'
--   * age derived for downstream segmentation

with src as (
    select * from {{ ref('bronze_customers') }}
)

select
    customer_id,
    full_name,
    {{ parse_legacy_date('date_of_birth') }}                       as date_of_birth,
    date_diff('year', {{ parse_legacy_date('date_of_birth') }}, current_date) as age_years,
    ssn_last4,
    case
        when kyc_status is null or trim(kyc_status) = '' then 'UNKNOWN'
        else upper(trim(kyc_status))
    end                                                            as kyc_status,
    upper(trim(risk_rating))                                       as risk_rating
from src
