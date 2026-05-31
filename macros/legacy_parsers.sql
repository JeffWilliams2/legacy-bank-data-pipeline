{#
  parse_legacy_date
  -----------------
  The legacy core-banking export stores dates as strings in FOUR different
  formats depending on which subsystem wrote the row:
      2021-03-04   (ISO)
      03/04/2021   (US slash)
      04-Mar-2021  (Oracle default)
      20210304     (compact / numeric)

  DuckDB's try_strptime returns NULL instead of erroring on a bad parse, so we
  COALESCE across every known format. The first one that matches wins.
  Returns a DATE (or NULL if nothing matches, which the tests will catch).
#}
{% macro parse_legacy_date(col) %}
    coalesce(
        try_strptime({{ col }}, '%Y-%m-%d'),
        try_strptime({{ col }}, '%m/%d/%Y'),
        try_strptime({{ col }}, '%d-%b-%Y'),
        try_strptime({{ col }}, '%Y%m%d')
    )::date
{% endmacro %}


{#
  clean_money
  -----------
  Balances/amounts arrive as strings, ~15% carrying a stray '$' and
  thousands-commas (e.g. "$12,345.67"). Strip non-numeric noise (keeping the
  sign and decimal point) and cast to a real decimal.
#}
{% macro clean_money(col) %}
    cast(
        regexp_replace({{ col }}, '[^0-9.\-]', '', 'g')
        as decimal(18, 2)
    )
{% endmacro %}
