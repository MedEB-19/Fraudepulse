"""Output sinks: idempotent MongoDB upsert (pymongo) and Kafka dead-letter queue."""
import logging

logger = logging.getLogger("fraudpulse.sinks")

BULK_SIZE = 1000


def write_partition(rows, uri: str, db: str, coll: str, collection=None) -> int:
    """Upsert one Spark partition into MongoDB. Runs on the executors.

    `_id` = "<kafka partition>-<kafka offset>" is deterministic, so if Spark replays
    a micro-batch after a failure the same documents are overwritten, not duplicated
    (at-least-once delivery + idempotent write = effectively-once result).
    """
    from pymongo import MongoClient, ReplaceOne

    client = None
    if collection is None:
        client = MongoClient(uri, serverSelectionTimeoutMS=10000)
        collection = client[db][coll]

    ops, written = [], 0
    for row in rows:
        doc = row.asDict(recursive=True)
        doc["_id"] = f"{doc.pop('kafka_partition')}-{doc.pop('kafka_offset')}"
        ops.append(ReplaceOne({"_id": doc["_id"]}, doc, upsert=True))
        if len(ops) >= BULK_SIZE:
            collection.bulk_write(ops, ordered=False)
            written += len(ops)
            ops = []
    if ops:
        collection.bulk_write(ops, ordered=False)
        written += len(ops)
    if client is not None:
        client.close()
    return written


def write_to_mongo(df, uri: str, db: str, coll: str) -> None:
    # Any exception propagates -> the micro-batch fails -> Spark retries it (no silent data loss).
    df.foreachPartition(lambda rows: write_partition(rows, uri, db, coll))


def write_to_dlq(df, broker: str, topic: str) -> None:
    """Send malformed raw messages to the dead-letter topic (batch Kafka write)."""
    (df.selectExpr("CAST(raw AS STRING) AS value")
       .write.format("kafka")
       .option("kafka.bootstrap.servers", broker)
       .option("topic", topic)
       .save())
