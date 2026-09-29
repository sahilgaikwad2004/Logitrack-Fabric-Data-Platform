# ============================================================
# LogiTrack | 01_bronze_ingestion  (schema-enabled Lakehouse version)
# Purpose: Land raw files (orders, shipments, regional sales)
#          into Bronze Delta tables under a 'bronze' schema,
#          untransformed, with ingestion metadata for lineage.
#
# Prereq: Upload orders.csv, shipments.csv, and the 4
#         regional_sales_*.csv files into:
#           Files/raw/orders/
#           Files/raw/shipments/
#           Files/raw/regional_sales/
#         inside this Lakehouse (via the Lakehouse "Files" UI).
# ============================================================

from pyspark.sql.functions import current_timestamp, input_file_name, lit

# ---- CELL 1: Create the bronze schema (if not already there) ----
spark.sql("CREATE SCHEMA IF NOT EXISTS bronze")

LAKEHOUSE_FILES = "Files/raw"

def land_csv_to_bronze(source_path: str, table_name: str, source_system: str):
    """
    Reads CSV(s) from a Files/ path, adds ingestion metadata,
    and writes/overwrites a Bronze Delta table under the 'bronze' schema.
    table_name should be schema-qualified, e.g. 'bronze.orders'
    """
    df = (
        spark.read
        .option("header", "true")
        .option("inferSchema", "true")   # Bronze = capture as-is; no schema enforcement yet
        .csv(source_path)
    )

    df_bronze = (
        df
        .withColumn("_ingested_at", current_timestamp())
        .withColumn("_source_file", input_file_name())
        .withColumn("_source_system", lit(source_system))
    )

    (
        df_bronze.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(table_name)
    )

    print(f"[OK] {table_name}: {df_bronze.count()} rows landed from {source_path}")
    return df_bronze


# ---- CELL 2: Orders ----
land_csv_to_bronze(
    source_path=f"{LAKEHOUSE_FILES}/orders/orders.csv",
    table_name="bronze.orders",
    source_system="orders_sql_export"
)

# ---- CELL 3: Shipments ----
land_csv_to_bronze(
    source_path=f"{LAKEHOUSE_FILES}/shipments/shipments.csv",
    table_name="bronze.shipments",
    source_system="shipments_sql_export"
)

# ---- CELL 4: Regional Sales (all 4 files at once) ----
land_csv_to_bronze(
    source_path=f"{LAKEHOUSE_FILES}/regional_sales/*.csv",
    table_name="bronze.regional_sales",
    source_system="regional_manual_upload"
)

# ---- CELL 5: Sanity check ----
print("\n--- Tables in bronze schema ---")
spark.sql("SHOW TABLES IN bronze").show(truncate=False)

print("\n--- Sample: bronze.orders ---")
spark.sql("SELECT * FROM bronze.orders LIMIT 5").show(truncate=False)

print("\n--- Row counts ---")
for t in ["bronze.orders", "bronze.shipments", "bronze.regional_sales"]:
    cnt = spark.sql(f"SELECT COUNT(*) as c FROM {t}").collect()[0]["c"]
    print(f"{t}: {cnt} rows")
