# ============================================================
# LogiTrack | 02_silver_cleaning
# Purpose: Clean Bronze data into trusted Silver tables:
#   - Deduplicate exact-duplicate rows
#   - Standardize region casing (East/West/North/South)
#   - Parse multiple date formats into a single DATE type
#   - Quarantine bad records (qty <= 0) into a separate table
#     instead of silently dropping them (this is the "data
#     quality with an audit trail" pattern real teams use)
#   - Trim whitespace on text fields
# ============================================================

from pyspark.sql.functions import (
    col, trim, upper, initcap, to_date, coalesce, lit, when, count as _count
)

spark.sql("CREATE SCHEMA IF NOT EXISTS silver")

VALID_REGIONS = ["East", "West", "North", "South"]

# ---- CELL 1: Helper - standardize region casing ----
def standardize_region(df, region_col="region"):
    """
    Messy input seen in Bronze: 'East', 'east', 'EAST', ' East',
    'North ', 'south', 'SOUTH', etc.
    Fix: trim whitespace, then title-case it so 'south' -> 'South'.
    """
    return df.withColumn(region_col, initcap(trim(col(region_col))))


# ---- CELL 2: Helper - parse multiple date formats into one DATE column ----
def standardize_date(df, date_col="order_date", new_col="order_date_clean"):
    """
    Bronze has 4 mixed formats: yyyy-MM-dd, MM/dd/yyyy, dd-MM-yyyy, yyyy/MM/dd
    Strategy: try each format with to_date(), coalesce to the first that
    successfully parses (the others return null for non-matching format).
    NOTE: dd-MM-yyyy vs MM-dd-yyyy is ambiguous for dates <=12 in both
    positions - for a portfolio project we document this assumption
    rather than silently guessing wrong.
    """
    parsed = coalesce(
        to_date(col(date_col), "yyyy-MM-dd"),
        to_date(col(date_col), "MM/dd/yyyy"),
        to_date(col(date_col), "dd-MM-yyyy"),
        to_date(col(date_col), "yyyy/MM/dd"),
    )
    return df.withColumn(new_col, parsed)


# ---- CELL 3: Clean bronze.orders -> silver.orders ----
orders_bronze = spark.table("bronze.orders")

orders_deduped = orders_bronze.dropDuplicates(
    ["order_id", "customer_id", "sku", "order_date", "quantity"]
)

orders_std = standardize_region(orders_deduped, "region")
orders_std = standardize_date(orders_std, "order_date", "order_date_clean")
orders_std = orders_std.withColumn("customer_name", trim(col("customer_name")))

# Quarantine: bad quantity (<=0) or unparseable date or missing customer_name
orders_quarantine = orders_std.filter(
    (col("quantity") <= 0) |
    (col("order_date_clean").isNull()) |
    (col("customer_name").isNull()) | (col("customer_name") == "")
).withColumn("_quarantine_reason",
    when(col("quantity") <= 0, "invalid_quantity")
    .when(col("order_date_clean").isNull(), "unparseable_date")
    .otherwise("missing_customer_name")
)

orders_clean = orders_std.filter(
    (col("quantity") > 0) &
    (col("order_date_clean").isNotNull()) &
    (col("customer_name").isNotNull()) & (col("customer_name") != "")
).drop("order_date").withColumnRenamed("order_date_clean", "order_date")

(orders_clean.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true").saveAsTable("silver.orders"))

(orders_quarantine.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true").saveAsTable("silver.orders_quarantine"))

print(f"[OK] silver.orders: {orders_clean.count()} clean rows "
      f"(from {orders_bronze.count()} bronze rows, "
      f"{orders_bronze.count() - orders_deduped.count()} exact duplicates removed)")
print(f"[OK] silver.orders_quarantine: {orders_quarantine.count()} rows flagged for review")


# ---- CELL 4: Clean bronze.shipments -> silver.shipments ----
shipments_bronze = spark.table("bronze.shipments")

shipments_deduped = shipments_bronze.dropDuplicates(
    ["shipment_id", "order_id", "ship_date", "status"]
)

shipments_std = standardize_region(shipments_deduped, "region")
shipments_std = standardize_date(shipments_std, "ship_date", "ship_date_clean")

shipments_quarantine = shipments_std.filter(col("ship_date_clean").isNull()) \
    .withColumn("_quarantine_reason", lit("unparseable_date"))

shipments_clean = shipments_std.filter(col("ship_date_clean").isNotNull()) \
    .drop("ship_date").withColumnRenamed("ship_date_clean", "ship_date")

(shipments_clean.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true").saveAsTable("silver.shipments"))

(shipments_quarantine.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true").saveAsTable("silver.shipments_quarantine"))

print(f"[OK] silver.shipments: {shipments_clean.count()} clean rows "
      f"(from {shipments_bronze.count()} bronze rows, "
      f"{shipments_bronze.count() - shipments_deduped.count()} exact duplicates removed)")
print(f"[OK] silver.shipments_quarantine: {shipments_quarantine.count()} rows flagged for review")


# ---- CELL 5: Clean bronze.regional_sales -> silver.regional_sales ----
sales_bronze = spark.table("bronze.regional_sales")
sales_std = standardize_region(sales_bronze, "region")
sales_std = standardize_date(sales_std, "week_ending", "week_ending_clean") \
    .drop("week_ending").withColumnRenamed("week_ending_clean", "week_ending")

(sales_std.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true").saveAsTable("silver.regional_sales"))

print(f"[OK] silver.regional_sales: {sales_std.count()} rows")


# ---- CELL 6: Data quality summary report ----
print("\n=== SILVER LAYER DATA QUALITY SUMMARY ===")
summary = spark.createDataFrame([
    ("orders", orders_bronze.count(), orders_clean.count(), orders_quarantine.count()),
    ("shipments", shipments_bronze.count(), shipments_clean.count(), shipments_quarantine.count()),
], ["table", "bronze_rows", "silver_clean_rows", "quarantined_rows"])
summary.show(truncate=False)

print("\n--- Region values after standardization (should be exactly 4) ---")
spark.table("silver.orders").select("region").distinct().show()

print("\n--- Sample quarantined orders (for review) ---")
spark.table("silver.orders_quarantine").select(
    "order_id", "quantity", "customer_name", "_quarantine_reason"
).show(10, truncate=False)
