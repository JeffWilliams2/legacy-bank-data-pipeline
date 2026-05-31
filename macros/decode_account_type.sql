{#
  decode_account_type
  --------------------
  Legacy core systems store account types as 3-letter codes. Downstream
  reporting (and humans) need the real label plus a regulatory grouping used
  for deposit-insurance aggregation.
#}
{% macro decode_account_type(code_col) %}
    case {{ code_col }}
        when 'CHK' then 'Checking'
        when 'SAV' then 'Savings'
        when 'MMA' then 'Money Market'
        when 'CD'  then 'Certificate of Deposit'
        when 'LOC' then 'Line of Credit'
        when 'IRA' then 'Retirement (IRA)'
        else 'Unknown'
    end
{% endmacro %}


{% macro account_is_deposit(code_col) %}
    {# LOC is credit (a liability of the customer), not an insured deposit #}
    case when {{ code_col }} in ('CHK', 'SAV', 'MMA', 'CD', 'IRA')
         then true else false end
{% endmacro %}
