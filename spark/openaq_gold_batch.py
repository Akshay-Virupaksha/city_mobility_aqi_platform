from pyspark.sql import SparkSession
from pyspark.sql.functions import col, to_timestamp, window, avg, count

spark = SparkSession.builder.appName("openaq-gold-batch").getOrCreate()
silver = spark.read.parquet("data/silver/openaq")

gold = (silver.withColumn("ts_ts", to_timestamp(col("ts")))
        .groupBy(window(col("ts_ts"), "15 minutes").alias("w"), col("location_id"))
        .agg(avg("value").alias("pm25_avg"), count("*").alias("samples"))
        .select("location_id", col("w.start").alias("window_start"),
                col("w.end").alias("window_end"), "pm25_avg", "samples"))

gold.write.mode("overwrite").parquet("data/gold/openaq_15min")
print("gold written")
