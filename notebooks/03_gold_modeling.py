# ============================================================
# LogiTrack | 03_gold_modeling
# Purpose: Build business-ready Gold tables from Silver:
#   - dim_customer: SCD Type 2 (tracks region/name changes over time)
#   - fact_orders: order line grain, joined to customer + date keys
#   - fact_shipments: shipment grain, joined to orders
#   - agg_regional_performance: pre-aggregated for fast dashboarding
# ============================================================

from pyspark.sql.functions import (
    col, current_timestamp, lit, row_number, sum as _sum, count as _count,
    avg as _avg, max as _max
)
from pyspark.sql.window import Window
from delta.tables import DeltaTable

spark.sql("CREATE SCHEMA IF NOT EXISTS gold")

# ---- CELL 1: Build dim_customer (SCD Type 2) ----
# Source: derive customer snapshot from silver.orders (customer_id, name, region)
# Real-world note: normally this would come from a dedicated customer source;
# here we derive it since orders is our richest customer signal.

orders_silver = spark.table("silver.orders")

# Take the LATEST known name/region per customer as "today's snapshot"
w = Window.partitionBy("customer_id").orderBy(col("order_date").desc())
customer_snapshot = (
    orders_silver
    .withColumn("_rn", row_number().over(w))
    .filter(col("_rn") == 1)
    .select("customer_id", "customer_name", "region", "city")
)

gold_table_exists = spark.catalog.tableExists("gold.dim_customer")

if not gold_table_exists:
    # First run: seed the SCD2 table
    dim_customer_init = (
        customer_snapshot
        .withColumn("effective_date", current_timestamp())
        .withColumn("end_date", lit(None).cast("timestamp"))
        .withColumn("is_current", lit(True))
        .withColumn("customer_sk", row_number().over(Window.orderBy("customer_id")))  # surrogate key
    )
    (dim_customer_init.write.format("delta").mode("overwrite")
        .option("overwriteSchema", "true").saveAsTable("gold.dim_customer"))
    print(f"[OK] gold.dim_customer seeded with {dim_customer_init.count()} customers (initial load)")
else:
    # Subsequent runs: proper SCD Type 2 merge
    # 1. Find customers whose name/region changed vs current record
    dim_current = spark.table("gold.dim_customer").filter(col("is_current") == True)

    changed = (
        customer_snapshot.alias("src")
        .join(dim_current.alias("cur"), "customer_id")
        .where(
            (col("src.customer_name") != col("cur.customer_name")) |
            (col("src.region") != col("cur.region"))
        )
        .select("src.customer_id")
    )

    new_customers = customer_snapshot.join(dim_current, "customer_id", "left_anti")

    delta_tbl = DeltaTable.forName(spark, "gold.dim_customer")

    # 2. Expire old versions of changed customers
    changed_ids = [r["customer_id"] for r in changed.collect()]
    if changed_ids:
        delta_tbl.update(
            condition=col("customer_id").isin(changed_ids) & (col("is_current") == True),
            set={"is_current": lit(False), "end_date": current_timestamp()}
        )

    # 3. Insert new rows for changed + brand-new customers
    max_sk = spark.table("gold.dim_customer").agg(_max("customer_sk")).collect()[0][0] or 0
    to_insert = customer_snapshot.join(
        spark.createDataFrame(changed_ids + [r["customer_id"] for r in new_customers.select("customer_id").collect()], "string").toDF("customer_id"),
        "customer_id", "inner"
    ).dropDuplicates(["customer_id"])

    to_insert_final = (
        to_insert
        .withColumn("effective_date", current_timestamp())
        .withColumn("end_date", lit(None).cast("timestamp"))
        .withColumn("is_current", lit(True))
        .withColumn("customer_sk", row_number().over(Window.orderBy("customer_id")) + lit(max_sk))
    )
    to_insert_final.write.format("delta").mode("append").saveAsTable("gold.dim_customer")

    print(f"[OK] gold.dim_customer SCD2 merge: {len(changed_ids)} changed, "
          f"{new_customers.count()} new customers added")


# ---- CELL 2: Build fact_orders ----
dim_customer_current = spark.table("gold.dim_customer").filter(col("is_current") == True)

fact_orders = (
    orders_silver.alias("o")
    .join(dim_customer_current.select("customer_id", "customer_sk").alias("c"), "customer_id")
    .select(
        col("o.order_id"),
        col("c.customer_sk"),
        col("o.customer_id"),
        col("o.region"),
        col("o.city"),
        col("o.order_date"),
        col("o.sku"),
        col("o.product_name"),
        col("o.quantity"),
        col("o.unit_price"),
        col("o.order_total"),
    )
)

(fact_orders.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true").saveAsTable("gold.fact_orders"))
print(f"[OK] gold.fact_orders: {fact_orders.count()} rows")


# ---- CELL 3: Build fact_shipments (joined to orders for region/customer context) ----
shipments_silver = spark.table("silver.shipments")

fact_shipments = (
    shipments_silver.alias("s")
    .join(orders_silver.select("order_id", "customer_id").alias("o"), "order_id", "left")
    .select(
        col("s.shipment_id"),
        col("s.order_id"),
        col("o.customer_id"),
        col("s.carrier"),
        col("s.vehicle_id"),
        col("s.ship_date"),
        col("s.status"),
        col("s.region"),
        col("s.delivery_days"),
    )
)

(fact_shipments.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true").saveAsTable("gold.fact_shipments"))
print(f"[OK] gold.fact_shipments: {fact_shipments.count()} rows")


# ---- CELL 4: Pre-aggregated regional performance (for fast Power BI dashboards) ----
agg_regional = (
    fact_orders.groupBy("region")
    .agg(
        _count("order_id").alias("total_orders"),
        _sum("order_total").alias("total_revenue"),
        _avg("order_total").alias("avg_order_value"),
    )
)

shipment_perf = (
    fact_shipments.filter(col("status") == "Delivered")
    .groupBy("region")
    .agg(_avg("delivery_days").alias("avg_delivery_days"))
)

agg_regional_final = agg_regional.join(shipment_perf, "region", "left")

(agg_regional_final.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true").saveAsTable("gold.agg_regional_performance"))

print(f"[OK] gold.agg_regional_performance: {agg_regional_final.count()} rows")


# ---- CELL 5: Verify everything ----
print("\n=== GOLD LAYER SUMMARY ===")
spark.sql("SHOW TABLES IN gold").show(truncate=False)

print("\n--- gold.agg_regional_performance ---")
spark.table("gold.agg_regional_performance").show(truncate=False)

print("\n--- gold.dim_customer sample (SCD2 columns) ---")
spark.table("gold.dim_customer").select(
    "customer_sk", "customer_id", "customer_name", "region", "is_current", "effective_date"
).show(5, truncate=False)
