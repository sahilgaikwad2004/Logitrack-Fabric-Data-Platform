# ============================================================
# LogiTrack | 01b_bronze_ingestion_optimized
# Purpose: Same as 01_bronze_ingestion.py, but with two
#          concrete cost/performance optimizations applied:
#
#   OPTIMIZATION 1: Explicit schema instead of inferSchema=True
#     - inferSchema forces Spark to do a full extra pass over
#       the file just to guess data types before the real read.
#       On small files this is invisible; at real data volumes
#       this doubles I/O cost for every single ingestion run.
#     - Defining the schema explicitly removes that entire pass.
#
#   OPTIMIZATION 2: Incremental load instead of full overwrite
#     - The original notebook did .mode("overwrite") every run,
#       reprocessing 100% of the data even if only a handful of
#       new rows arrived since yesterday.
#     - This version only processes files not already ingested,
#       tracked via a simple watermark table. In a real pipeline
#       with daily-arriving files, this is the difference between
#       a job that costs the same every day forever, and one that
#       shrinks to "just today's delta" after the first run.
#
# NOTE: table names now use bronze_v2 schema so this can run
# side-by-side with your original bronze tables for comparison.
# ============================================================

from pyspark.sql.functions import current_timestamp, input_file_name, lit
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, DoubleType
)
import time

spark.sql("CREATE SCHEMA IF NOT EXISTS bronze_v2")
spark.sql("CREATE SCHEMA IF NOT EXISTS meta")  # for watermark tracking

LAKEHOUSE_FILES = "Files/raw"

# ---- CELL 1: Explicit schemas (Optimization 1) ----
orders_schema = StructType([
    StructField("order_id", StringType(), True),
    StructField("customer_id", StringType(), True),
    StructField("customer_name", StringType(), True),
    StructField("region", StringType(), True),
    StructField("city", StringType(), True),
    StructField("order_date", StringType(), True),  # kept as string; parsed properly in Silver
    StructField("sku", StringType(), True),
    StructField("product_name", StringType(), True),
    StructField("quantity", IntegerType(), True),
    StructField("unit_price", DoubleType(), True),
    StructField("order_total", DoubleType(), True),
])

shipments_schema = StructType([
    StructField("shipment_id", StringType(), True),
    StructField("order_id", StringType(), True),
    StructField("carrier", StringType(), True),
    StructField("vehicle_id", StringType(), True),
    StructField("ship_date", StringType(), True),
    StructField("status", StringType(), True),
    StructField("region", StringType(), True),
    StructField("delivery_days", IntegerType(), True),
])

regional_sales_schema = StructType([
    StructField("region", StringType(), True),
    StructField("week_ending", StringType(), True),
    StructField("total_orders", IntegerType(), True),
    StructField("total_revenue", DoubleType(), True),
    StructField("notes", StringType(), True),
])


# ---- CELL 2: Watermark helper functions (Optimization 2) ----
def get_processed_files(table_name: str) -> set:
    """Returns the set of source files already ingested for this table."""
    watermark_table = f"meta.{table_name}_watermark"
    if spark.catalog.tableExists(watermark_table):
        rows = spark.table(watermark_table).select("file_path").collect()
        return {r["file_path"] for r in rows}
    return set()


def mark_files_processed(table_name: str, file_paths: list):
    """Records which files have now been ingested, for next run's incremental check."""
    watermark_table = f"meta.{table_name}_watermark"
    df = spark.createDataFrame([(f,) for f in file_paths], ["file_path"]) \
        .withColumn("processed_at", current_timestamp())
    df.write.format("delta").mode("append").saveAsTable(watermark_table)


def land_csv_to_bronze_incremental(source_path: str, table_name: str,
                                     schema: StructType, source_system: str,
                                     watermark_key: str):
    """
    Incremental version: only reads files not already recorded in the
    watermark table. First run processes everything (nothing recorded
    yet); subsequent runs only touch new files.
    """
    # Read all files with a path column, then filter out any file
    # already recorded in the watermark table from a prior run.
    df_all = (
        spark.read
        .option("header", "true")
        .schema(schema)
        .csv(source_path)
        .withColumn("_source_file", input_file_name())
    )

    processed = get_processed_files(watermark_key)

    if processed:
        df_new = df_all.filter(~df_all["_source_file"].isin(processed))
        write_mode = "append"
    else:
        df_new = df_all
        write_mode = "overwrite"

    new_file_count = df_new.select("_source_file").distinct().count()

    if new_file_count == 0:
        print(f"[SKIP] {table_name}: no new files since last run \u2014 0 CU spent on this table")
        return

    df_bronze = (
        df_new
        .withColumn("_ingested_at", current_timestamp())
        .withColumn("_source_system", lit(source_system))
    )

    (
        df_bronze.write
        .format("delta")
        .mode(write_mode)
        .option("mergeSchema", "true")
        .saveAsTable(table_name)
    )

    new_files = [r["_source_file"] for r in df_new.select("_source_file").distinct().collect()]
    mark_files_processed(watermark_key, new_files)

    print(f"[OK] {table_name}: {df_bronze.count()} rows from {new_file_count} new file(s) "
          f"({write_mode} mode)")


# ---- CELL 3: Run with timing to compare against the original ----
t0 = time.time()

land_csv_to_bronze_incremental(
    f"{LAKEHOUSE_FILES}/orders/*.csv", "bronze_v2.orders",
    orders_schema, "orders_sql_export", "orders"
)
land_csv_to_bronze_incremental(
    f"{LAKEHOUSE_FILES}/shipments/*.csv", "bronze_v2.shipments",
    shipments_schema, "shipments_sql_export", "shipments"
)
land_csv_to_bronze_incremental(
    f"{LAKEHOUSE_FILES}/regional_sales/*.csv", "bronze_v2.regional_sales",
    regional_sales_schema, "regional_manual_upload", "regional_sales"
)

elapsed = time.time() - t0
print(f"\n[TIMING] Optimized ingestion completed in {elapsed:.1f} seconds")
print("Compare this against the original 01_bronze_ingestion.py run time")
print("(check the notebook's cell execution time shown under each cell, or Monitor Hub)")

# ---- CELL 4: Run it AGAIN immediately to prove incremental skip works ----
print("\n=== RUNNING AGAIN to demonstrate incremental skip ===")
t1 = time.time()
land_csv_to_bronze_incremental(
    f"{LAKEHOUSE_FILES}/orders/*.csv", "bronze_v2.orders",
    orders_schema, "orders_sql_export", "orders"
)
elapsed2 = time.time() - t1
print(f"[TIMING] Second run (no new data) completed in {elapsed2:.1f} seconds")
print("This should be dramatically faster than the first run \u2014 that gap IS the cost savings")
