# Quick data quality check: are there hidden leading/trailing spaces in 'region'?
from pyspark.sql.functions import col, length, concat, lit

spark.table("silver.orders").select(
    col("region"),
    length(col("region")).alias("char_length"),
    concat(lit("["), col("region"), lit("]")).alias("bracketed")  # brackets make stray spaces visible
).distinct().show(truncate=False)
