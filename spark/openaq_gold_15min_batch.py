import os
from pyspark.sql import SparkSession, functions as F

SRC_SILVER = os.getenv("SRC_SILVER", "/app/data/silver/openaq")
OUT        = os.getenv("OUT", "/app/data/gold/openaq_15min")
WINDOW     = os.getenv("WINDOW", "15 minutes")  # e.g., "15 minutes"

spark = (SparkSession.builder
         .appName("OpenAQ Gold 15min")
         .config("spark.sql.session.timeZone","UTC")
         .getOrCreate())

df = spark.read.parquet(SRC_SILVER)

ts_col = "ts_ts" if "ts_ts" in df.columns else "ts"
df = df.withColumn("ts_ts", F.col(ts_col).cast("timestamp"))


df = (df
      .filter(F.col("parameter_id") == 2)
      .filter(F.col("ts_ts").isNotNull())
      .filter(F.col("value").isNotNull())
      .filter(F.col("lat").isNotNull() & F.col("lon").isNotNull())
      .filter((F.col("value") >= 0.0) & (F.col("value") <= 1000.0))
     )

agg = (df
       .groupBy(F.window("ts_ts", WINDOW).alias("w"), "location_id")
       .agg(F.avg("value").alias("pm25_avg"),
            F.count("*").alias("samples"))
       .select("location_id",
               F.col("w.start").alias("window_start"),
               "pm25_avg","samples")
       .withColumn("event_date", F.to_date("window_start"))
       .select("event_date","location_id","window_start","pm25_avg","samples")
      )


(agg.write
 .mode("overwrite")              
 .partitionBy("event_date")
 .parquet(OUT))

spark.stop()
