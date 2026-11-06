"""PySpark Structured Streaming job: Kafka -> XGBoost (inside Spark) -> MongoDB.

One streaming query, one checkpoint. Everything for a micro-batch happens in
`process_batch` so a batch is either fully handled or retried as a whole.
"""
import logging
import os
import sys
import time

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from xgboost.spark import SparkXGBClassifierModel

from fraudpulse.config import Settings, load_settings
from fraudpulse.features import REQUIRED_COLS
from fraudpulse.metrics import PipelineMetrics
from fraudpulse.scoring import score_dataframe
from fraudpulse.sinks import write_to_dlq, write_to_mongo
from fraudpulse.spark_features import INPUT_SCHEMA

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
log = logging.getLogger("fraudpulse.stream")


def split_valid_invalid(batch_df):
    """Parse the raw Kafka value as JSON. Rows missing any required field are 'invalid'."""
    parsed = batch_df.select(
        F.col("partition").alias("kafka_partition"),
        F.col("offset").alias("kafka_offset"),
        F.col("value").cast("string").alias("raw"),
    ).withColumn("d", F.from_json("raw", INPUT_SCHEMA))

    is_valid = F.lit(True)
    for c in REQUIRED_COLS:
        is_valid = is_valid & F.col(f"d.{c}").isNotNull()

    valid = parsed.filter(is_valid).select("kafka_partition", "kafka_offset", "d.*")
    invalid = parsed.filter(~is_valid).select("raw")
    return valid, invalid


def make_batch_processor(cfg: Settings, model, metrics: PipelineMetrics):
    def process_batch(batch_df, batch_id: int) -> None:
        t0 = time.time()
        valid, invalid = split_valid_invalid(batch_df)

        scored = score_dataframe(valid, model, cfg.fraud_threshold, cfg.rule_amount).persist()
        try:
            agg = scored.agg(
                F.count("*").alias("n"),
                F.sum(F.col("fraud_flag").cast("int")).alias("flagged"),
                F.sum((F.col("risk_level") == "HIGH").cast("int")).alias("high"),
            ).first()
            n, flagged, high = agg["n"] or 0, agg["flagged"] or 0, agg["high"] or 0
            if n:
                write_to_mongo(scored, cfg.mongo_uri, cfg.mongo_db, cfg.mongo_collection)
        finally:
            scored.unpersist()

        bad = invalid.count()
        if bad:
            write_to_dlq(invalid, cfg.kafka_broker, cfg.kafka_dlq_topic)

        secs = time.time() - t0
        metrics.record_batch(n, bad, flagged, high, secs)
        log.info("batch=%s scored=%s flagged=%s high=%s dlq=%s time=%.1fs", batch_id, n, flagged, high, bad, secs)

    return process_batch


def wait_for_model(model_path: str, timeout_s: int = 3600) -> None:
    """The model is produced by the training job; wait for it instead of crashing."""
    waited = 0
    while not os.path.exists(os.path.join(model_path, "model")):
        if waited >= timeout_s:
            sys.exit(f"Model not found at {model_path}. Run the training job first.")
        log.info("Waiting for model at %s (run `make train`)...", model_path)
        time.sleep(10)
        waited += 10


def main() -> None:
    cfg = load_settings()
    model_path = os.path.join(cfg.model_dir, "spark_model")
    wait_for_model(model_path)

    spark = (SparkSession.builder.appName("FraudPulseStream")
             .config("spark.sql.session.timeZone", "UTC")
             .config("spark.sql.shuffle.partitions", "6")
             .getOrCreate())
    spark.sparkContext.setLogLevel("WARN")

    model = SparkXGBClassifierModel.load("file://" + os.path.abspath(model_path))
    metrics = PipelineMetrics(cfg.pushgateway)

    raw = (spark.readStream.format("kafka")
           .option("kafka.bootstrap.servers", cfg.kafka_broker)
           .option("subscribe", cfg.kafka_topic)
           .option("startingOffsets", cfg.starting_offsets)
           .option("maxOffsetsPerTrigger", cfg.max_offsets_per_trigger)
           .option("failOnDataLoss", "false")
           .load())

    query = (raw.writeStream
             .foreachBatch(make_batch_processor(cfg, model, metrics))
             .option("checkpointLocation", cfg.checkpoint_dir)
             .trigger(processingTime=f"{cfg.trigger_seconds} seconds")
             .start())
    log.info("Streaming query started: topic=%s -> mongo=%s.%s", cfg.kafka_topic, cfg.mongo_db, cfg.mongo_collection)
    query.awaitTermination()


if __name__ == "__main__":
    main()
