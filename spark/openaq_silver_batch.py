from pyspark.sql import SparkSession
from pyspark.sql.functions import col, to_timestamp, to_date, row_number
from pyspark.sql.window import Window

spark = SparkSession.builder.appName("openaq-silver-batch").getOrCreate()
bronze = spark.read.parquet("data/bronze/openaq")

df = (bronze
      .withColumn("ts_ts", to_timestamp(col("ts")))
      .withColumn("ingested_at_ts", to_timestamp(col("ingested_at")))
      .filter(col("lat").isNotNull() & col("lon").isNotNull() & col("ts_ts").isNotNull())
      .filter((col("value") >= 0) & (col("value") <= 1000)))

w = Window.partitionBy("location_id","ts_ts").orderBy(col("ingested_at_ts").desc())
silver = (df.withColumn("rn", row_number().over(w)).filter(col("rn")==1).drop("rn")
          .withColumn("event_date", to_date(col("ts_ts"))))

silver.write.mode("append").partitionBy("event_date").parquet("data/silver/openaq")
print("silver written")
