# Data Dictionary

All tables live in the schema-enabled Lakehouse `logitrack_lakehouse` and are stored as Delta. Lineage columns appear on every Bronze table.

## Lineage columns (all Bronze tables)

| Column | Type | Meaning |
|---|---|---|
| `_ingested_at` | timestamp | When the row was loaded |
| `_source_file` | string | Full path of the file the row came from |
| `_source_system` | string | Label of the simulated source (`orders_sql_export`, `shipments_sql_export`, `regional_manual_upload`) |

## bronze.orders, silver.orders

| Column | Bronze | Silver | Notes |
|---|---|---|---|
| `order_id` | string | string | Business key, `ORD-000001` format |
| `customer_id` | string | string | `CUST-00001` format |
| `customer_name` | string | string | Blank in about 3% of source rows; blanks are quarantined in Silver |
| `region` | string | string | Bronze has mixed casing and stray spaces; Silver is exactly East, West, North or South |
| `city` | string | string | |
| `order_date` | string | date | Bronze holds four text formats; Silver parses to `DATE` |
| `sku` | string | string | |
| `product_name` | string | string | |
| `quantity` | int | int | Values <= 0 are quarantined in Silver |
| `unit_price` | double | double | |
| `order_total` | double | double | `quantity * unit_price` |

**silver.orders_quarantine** has the same columns plus the pre-parse `order_date` text, `order_date_clean`, and `_quarantine_reason` (`invalid_quantity`, `unparseable_date` or `missing_customer_name`).

## bronze.shipments, silver.shipments

| Column | Type | Notes |
|---|---|---|
| `shipment_id` | string | `SHIP-000001` format |
| `order_id` | string | Links to orders |
| `carrier` | string | FedEx, UPS, DHL or USPS |
| `vehicle_id` | string | `VH-001` to `VH-020` |
| `ship_date` | string in Bronze, date in Silver | Same four source formats |
| `status` | string | Delivered, In Transit, Delayed or Cancelled |
| `region` | string | Standardised in Silver |
| `delivery_days` | int | Blank in about 5% of source rows |

`silver.shipments_quarantine` holds rows with an unparseable `ship_date` (zero rows in the run recorded here).

## bronze.regional_sales, silver.regional_sales

| Column | Type | Notes |
|---|---|---|
| `region` | string | Standardised in Silver |
| `week_ending` | string in Bronze, date in Silver | |
| `total_orders` | int | |
| `total_revenue` | double | |
| `notes` | string | Free text, often blank |

## Gold

**gold.dim_customer** (SCD Type 2)

| Column | Type | Meaning |
|---|---|---|
| `customer_sk` | int | Surrogate key |
| `customer_id` | string | Business key |
| `customer_name`, `region`, `city` | string | Latest known values at load |
| `effective_date` | timestamp | When this version became current |
| `end_date` | timestamp | Null while current |
| `is_current` | boolean | True for the active version |

**gold.fact_orders**: `order_id`, `customer_sk`, `customer_id`, `region`, `city`, `order_date`, `sku`, `product_name`, `quantity`, `unit_price`, `order_total`.

**gold.fact_shipments**: `shipment_id`, `order_id`, `customer_id`, `carrier`, `vehicle_id`, `ship_date`, `status`, `region`, `delivery_days`.

**gold.agg_regional_performance**: `region`, `total_orders`, `total_revenue`, `avg_order_value`, `avg_delivery_days` (delivered shipments only).

## rag.policy_chunks

| Column | Type | Meaning |
|---|---|---|
| `chunk_id` | long | Sequence number |
| `chunk_text` | string | One policy paragraph |
| `embedding` | array of float | 1,536-dimension vector |

## meta.*_watermark

Created by the optimised ingestion notebook, one per source (`orders`, `shipments`, `regional_sales`).

| Column | Type | Meaning |
|---|---|---|
| `file_path` | string | A source file already ingested |
| `processed_at` | timestamp | When it was recorded |

## bronze_v2.*

Same columns as Bronze, loaded with an explicit schema and the incremental pattern. `order_date`, `ship_date` and `week_ending` remain text until Silver.

## Data quality rules summary

| Rule | Applies to | Action |
|---|---|---|
| Exact duplicate on business-key columns | orders, shipments | Drop |
| Region not in the four valid values after trim and title-case | all | Not currently enforced; verified manually |
| Quantity <= 0 | orders | Quarantine |
| Order or ship date cannot be parsed | orders, shipments | Quarantine |
| Missing customer name | orders | Quarantine |
