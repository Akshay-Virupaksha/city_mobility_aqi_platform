import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, to_timestamp, to_date
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, LongType, IntegerType
)

KAFKA = os.getenv("KAFKA_BROKER", "kafka:9092")
TOPIC = "openaq.measurements"

schema = StructType([
    StructField("source",        StringType()),
    StructField("parameter_id",  IntegerType()),
    StructField("sensor_id",     LongType()),
    StructField("location_id",   LongType()),
    StructField("value",         DoubleType()),
    StructField("lat",           DoubleType()),
    StructField("lon",           DoubleType()),
    StructField("ts",            StringType()),
    StructField("ingested_at",   StringType()),
])

spark = (SparkSession.builder
    .appName("openaq-kafka-to-parquet")
    .config("spark.sql.shuffle.partitions", "4")
    .getOrCreate())

# 1) Read stream from Kafka (value is JSON string)
raw = (spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", KAFKA)
    .option("subscribe", TOPIC)
    .option("startingOffsets", "latest")
    .load()
    .selectExpr("CAST(value AS STRING) AS json"))

# 2) Parse JSON → typed columns
parsed = raw.select(from_json(col("json"), schema).alias("r")).select("r.*")

# 3) Type tidy: cast timestamps and add a date partition
tidy = (parsed
    .withColumn("ts_ts", to_timestamp(col("ts")))           # event time
    .withColumn("ingested_at_ts", to_timestamp(col("ingested_at")))
    .withColumn("event_date", to_date(col("ts_ts"))))


out_path = "/app/data/bronze/openaq"
chk_path = "/app/data/_chk/openaq_bronze"

query = (tidy.writeStream
    .format("parquet")
    .option("path", out_path)
    .option("checkpointLocation", chk_path)
    .partitionBy("event_date")      
    .outputMode("append")
    .start())

query.awaitTermination()
