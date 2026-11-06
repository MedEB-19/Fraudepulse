"""Central configuration, read from environment variables (see .env.example)."""
import os
from dataclasses import dataclass


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    kafka_broker: str
    kafka_topic: str
    kafka_dlq_topic: str
    starting_offsets: str
    max_offsets_per_trigger: int
    trigger_seconds: int
    mongo_uri: str
    mongo_db: str
    mongo_collection: str
    model_dir: str
    checkpoint_dir: str
    fraud_threshold: float
    rule_amount: float
    pushgateway: str


def load_settings() -> Settings:
    return Settings(
        kafka_broker=_env("KAFKA_BROKER", "kafka:29092"),
        kafka_topic=_env("KAFKA_TOPIC", "fraud-transactions"),
        kafka_dlq_topic=_env("KAFKA_DLQ_TOPIC", "fraud-transactions-dlq"),
        starting_offsets=_env("STARTING_OFFSETS", "earliest"),
        max_offsets_per_trigger=int(_env("MAX_OFFSETS_PER_TRIGGER", "5000")),
        trigger_seconds=int(_env("TRIGGER_SECONDS", "5")),
        mongo_uri=_env("MONGO_URI", "mongodb://mongodb:27017/"),
        mongo_db=_env("MONGO_DB", "fraud_db"),
        mongo_collection=_env("MONGO_COLLECTION", "transactions"),
        model_dir=_env("MODEL_DIR", "/app/models"),
        checkpoint_dir=_env("CHECKPOINT_DIR", "/app/checkpoints/stream"),
        fraud_threshold=float(_env("FRAUD_THRESHOLD", "0.5")),
        rule_amount=float(_env("RULE_AMOUNT", "200000")),
        pushgateway=_env("PROMETHEUS_PUSHGATEWAY", ""),
    )
