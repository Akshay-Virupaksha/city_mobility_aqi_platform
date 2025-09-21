import os, sys
from pyspark.sql import SparkSession

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_DB   = os.getenv("POSTGRES_SERVING_DB", "serving_dw")
POSTGRES_USER = os.getenv("POSTGRES_USER", "mobility")
POSTGRES_PWD  = os.getenv("POSTGRES_PASSWORD", "mobility_pwd")
JDBC_URL = f"jdbc:postgresql://{POSTGRES_HOST}:5432/{POSTGRES_DB}"

spark = (SparkSession.builder
         .appName("openaq-gold-to-postgres")
         .config("spark.sql.shuffle.partitions", "4")
         .getOrCreate())

df = spark.read.parquet("data/gold/openaq_15min")

print(">>> GOLD schema:")
df.printSchema()
cnt = df.count()
print(">>> GOLD row count:", cnt)
if cnt == 0:
    print("No rows found in gold; aborting write.")
    sys.exit(0)

(df.write.format("jdbc")
   .option("url", JDBC_URL)
   .option("dbtable", "aqi.openaq_15min")
   .option("user", POSTGRES_USER)
   .option("password", POSTGRES_PWD)
   .option("driver", "org.postgresql.Driver")
   .option("truncate", "true")     
   .mode("overwrite")
   .save())

print(">>> Loaded aqi.openaq_15min to Postgres")