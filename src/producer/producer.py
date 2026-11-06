"""Kafka producer: replays the PaySim CSV as a live transaction stream (pure Python)."""
import csv
import json
import logging
import os
import time

from confluent_kafka import KafkaException, Producer
from prometheus_client import Counter, Histogram, start_http_server

RECORDS = Counter("fraudpulse_records_produced_total", "Records delivered to Kafka")
ERRORS = Counter("fraudpulse_produce_errors_total", "Records that failed delivery")
LATENCY = Histogram("fraudpulse_delivery_latency_seconds", "Produce->ack latency")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s - %(message)s")
log = logging.getLogger("fraudpulse.producer")


def make_producer(brokers: str, retries: int = 10) -> Producer:
    backoff = 2
    for attempt in range(1, retries + 1):
        try:
            p = Producer({
                "bootstrap.servers": brokers,
                "acks": "all",
                "enable.idempotence": True,           # no duplicates on retry
                "compression.type": os.environ.get("PRODUCER_COMPRESSION", "lz4"),
                "linger.ms": int(os.environ.get("PRODUCER_LINGER_MS", "10")),
                "batch.size": int(os.environ.get("PRODUCER_BATCH_SIZE", "32768")),
                "queue.buffering.max.messages": 100000,
            })
            p.list_topics(timeout=5)
            log.info("Connected to Kafka at %s", brokers)
            return p
        except Exception as exc:  # noqa: BLE001
            log.warning("Kafka not ready (%s) attempt %d/%d, retry in %ds", exc, attempt, retries, backoff)
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)
    raise RuntimeError("Could not connect to Kafka")


def row_to_payload(row: dict) -> dict:
    return {
        "step": int(row["step"]), "type": row["type"], "amount": float(row["amount"]),
        "nameOrig": row["nameOrig"], "oldbalanceOrg": float(row["oldbalanceOrg"]),
        "newbalanceOrig": float(row["newbalanceOrig"]), "nameDest": row["nameDest"],
        "oldbalanceDest": float(row["oldbalanceDest"]), "newbalanceDest": float(row["newbalanceDest"]),
        "isFraud": int(row.get("isFraud") or 0), "isFlaggedFraud": int(row.get("isFlaggedFraud") or 0),
    }


def main() -> None:
    start_http_server(8001)
    brokers = os.environ.get("KAFKA_BROKER", "kafka:29092")
    topic = os.environ.get("KAFKA_TOPIC", "fraud-transactions")
    delay = float(os.environ.get("STREAM_DELAY_SECONDS", "0.05"))
    csv_file = os.environ.get("PRODUCER_DATA", "/app/data/paysim.csv")
    loop = os.environ.get("PRODUCER_LOOP", "false").lower() == "true"
    max_records = int(os.environ.get("MAX_RECORDS", "0"))  # 0 = unlimited

    if not os.path.exists(csv_file):
        raise SystemExit(f"Dataset not found: {csv_file} (see data/README.md)")
    producer = make_producer(brokers)

    def on_delivery(err, msg, t0):
        LATENCY.observe(time.time() - t0)
        if err is not None:
            ERRORS.inc(); log.error("Delivery failed: %s", err)
        else:
            RECORDS.inc()

    sent = 0
    try:
        while True:
            with open(csv_file, newline="") as fh:
                for row in csv.DictReader(fh):
                    try:
                        payload = row_to_payload(row)
                    except (ValueError, KeyError) as exc:
                        log.warning("Skipping bad row: %s", exc); continue
                    t0 = time.time()
                    try:
                        producer.produce(topic, key=payload["nameOrig"],
                                         value=json.dumps(payload).encode(),
                                         on_delivery=lambda e, m, t=t0: on_delivery(e, m, t))
                    except BufferError:
                        producer.poll(1)       # local queue full -> let it drain
                        continue
                    except KafkaException as exc:
                        log.error("Kafka error: %s", exc); continue
                    producer.poll(0)
                    sent += 1
                    if sent % 1000 == 0:
                        log.info("Produced %d messages", sent)
                    if max_records and sent >= max_records:
                        return
                    if delay > 0:
                        time.sleep(delay)
            if not loop:
                break
    except KeyboardInterrupt:
        pass
    finally:
        producer.flush(10)
        log.info("Producer closed after %d messages", sent)


if __name__ == "__main__":
    main()
