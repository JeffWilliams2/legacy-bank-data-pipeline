{#
  By default dbt names schemas "{target_schema}_{custom}". For a clean
  medallion layout we want the custom names used verbatim: raw, bronze,
  silver, gold. This is the standard documented override.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
