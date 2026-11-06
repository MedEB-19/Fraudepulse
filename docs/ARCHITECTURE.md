# FraudPulse v2 — How everything works

## 1. The big picture

```
 PaySim CSV ──► Producer ──► Kafka topic ──► PySpark stream job ──► MongoDB ──► Streamlit
 (6.3M rows)   (Python)      fraud-transactions   │  ▲                            dashboard
                                                  │  └── model trained by PySpark + XGBoost
                                                  └──► Kafka DLQ topic (bad messages)
```

Two Spark applications run on the same Spark standalone cluster (1 master + 2 workers):

| App | File | When | What |
|---|---|---|---|
| Training | `src/jobs/train.py` | on demand (`make train`) | trains XGBoost *inside Spark*, writes the model |
| Streaming | `src/jobs/stream.py` | always on | reads Kafka, scores with the model, writes MongoDB |

## 2. Step by step

### 2.1 Producer (`src/producer/producer.py`)
Reads `paysim.csv` row by row and publishes each transaction as JSON to the Kafka topic
`fraud-transactions`. The message key is `nameOrig` (the sending customer), so all transactions of one
customer go to the same partition and stay ordered. The producer is configured with `acks=all` and
`enable.idempotence=true`, so retries cannot create duplicates. It exposes Prometheus metrics on port 8001.
`STREAM_DELAY_SECONDS` controls the speed (default 0.05 s ≈ 20 tx/s).

### 2.2 Kafka (KRaft mode)
One broker acting as broker+controller (no ZooKeeper). Topics are created by the `kafka-init` container:
`fraud-transactions` (6 partitions) and `fraud-transactions-dlq` (dead-letter queue). For production you would
use 3 brokers and replication factor 3.

### 2.3 Training (`src/jobs/train.py`) — XGBoost inside Spark
1. Spark reads the CSV with an explicit schema (`spark_features.INPUT_SCHEMA`).
2. `add_features` creates 6 engineered features with Spark SQL expressions (no UDF):
   `balance_drained`, `dest_balance_unchanged`, `amount_to_balance_ratio`, `hour_of_day`,
   `is_transfer_or_cashout`, `type_encoded` (fixed mapping).
3. The 11 features are packed into one dense `features` vector column.
4. 80/20 random split (seed 42). Class imbalance (~0.13 % fraud in PaySim) is handled with
   `scale_pos_weight = legit / fraud`.
5. `xgboost.spark.SparkXGBClassifier(num_workers=2, tree_method="hist", ...)` trains **distributed**:
   each XGBoost worker is a Spark *barrier task*; workers exchange gradient statistics (Rabit/tracker)
   so the result is one model trained on all partitions.
6. Evaluation on the test split: AUC-ROC, AUC-PR (the metric that matters for rare fraud), precision,
   recall, F1 and the confusion matrix at the chosen threshold → `models/metrics.json`.
7. Artefacts written to `models/`:
   - `spark_model/` — Spark ML model, loaded by the streaming job
   - `fraud_model.json` — plain XGBoost booster, loaded by the REST server
   - `reference_stats.json` — training feature distributions (for drift detection)
   - `metrics.json`, `feature_cols.json`
8. If `MLFLOW_TRACKING_URI` is set, params/metrics/artefacts are logged to MLflow (optional).

### 2.4 Streaming (`src/jobs/stream.py`) — scoring in real time
Spark Structured Streaming reads Kafka in micro-batches (every 5 s, at most 5000 records per batch —
this is the back-pressure control). For every micro-batch `process_batch` does:

1. **Parse** the Kafka `value` as JSON using the schema. A record is *invalid* if it is not JSON or a
   required field is missing.
2. **Features**: the same `add_features` as training.
3. **Score**: `SparkXGBClassifierModel.transform` runs XGBoost on the executors (pandas UDF) and returns
   `fraud_probability`.
4. **Decide** (`fraudpulse/scoring.py`):
   - `model_flag` = probability > threshold (default 0.5)
   - `rule_engine_flag` = TRANSFER/CASH_OUT, origin emptied, destination unchanged, amount > 200 000
   - `fraud_flag` = model OR rule
   - `risk_level` = HIGH (p > 0.8 or rule) / MEDIUM (p > threshold) / LOW
5. **Store** valid records in MongoDB (`fraud_db.transactions`) from the executors with pymongo
   `bulk_write`.
6. **Dead-letter**: invalid raw messages are written to the Kafka DLQ topic instead of being lost.
7. **Metrics**: counters/gauges are pushed to the Pushgateway.

**Delivery guarantee.** Spark guarantees at-least-once for `foreachBatch`: after a crash a micro-batch may
be replayed. Each Mongo document uses `_id = "<kafka partition>-<kafka offset>"` and is written with
*upsert*, so a replay overwrites the same documents → no duplicates (effectively-once result).
If MongoDB is down the exception is **not swallowed**: the batch fails, Spark restarts it from the
checkpoint and nothing is lost (v1 swallowed write errors).

**Checkpoint.** `spark_checkpoints` volume stores the Kafka offsets that were committed. A restart resumes
exactly where it stopped. `STARTING_OFFSETS=earliest` only matters for the very first start.

### 2.5 MongoDB
Collection `transactions` with indexes on `processed_at`, `fraud_flag`, `risk_level`, `type`, `amount`,
`nameOrig` (`src/mongo/init_mongo.js`). A TTL index is included (commented) for production retention.

### 2.6 Dashboard (Streamlit)
Reads the latest 10 000 documents from MongoDB and shows KPIs, a live alert feed, charts by type / risk
level / time step, model-vs-rule overlap and a transaction explorer.

### 2.7 Model server (FastAPI)
`POST /predict` scores one transaction with the plain XGBoost booster `fraud_model.json`, using
`fraudpulse.features.row_features` — the same formulas as Spark. It hot-reloads when a new model file
appears. This is the "online" path next to the "streaming" path.

### 2.8 Observability (optional, `make up-full`)
The stream job pushes metrics after each batch → Pushgateway → Prometheus → Grafana dashboard
"FraudPulse Pipeline" (throughput, flagged/sec, batch duration, batch size, DLQ count, producer rate).
MLflow tracks training runs.

### 2.9 Drift monitoring (`src/monitoring/drift_check.py`)
Computes the Population Stability Index (PSI) per feature between the training distribution and the last
20 000 scored transactions. PSI < 0.1 stable, 0.1–0.25 watch, > 0.25 drift → retrain with `make train`.

## 3. Design decisions worth knowing (interview-ready)

| Decision | Why |
|---|---|
| PySpark + `xgboost.spark` instead of Scala + XGBoost4J | one language, one toolchain, no sbt/JAR build; same distributed training |
| One shared feature definition | prevents train/serve skew; verified by a test |
| `foreachBatch` + one checkpoint | whole micro-batch handled atomically; easy to add sinks |
| Idempotent upsert keyed by Kafka offset | effectively-once despite at-least-once delivery |
| DLQ topic | bad data is isolated, never blocks the stream, never silently dropped |
| `scale_pos_weight` + AUC-PR | PaySim is ~0.13 % fraud; accuracy/ROC alone are misleading |
| Rule engine next to the model | transparent business rule catches the obvious pattern even if the model misses it |
| Dense feature vector | with sparse vectors zeros could be confused with missing values |
| Pushgateway | the Spark driver is not a long-lived scrape target |

## 4. Differences from v1
- Scala/sbt/XGBoost4J removed; PySpark + `SparkXGBClassifier`.
- Fixed type-encoding skew (v1 built the mapping from `unique()` order in training and a hard-coded one in the server).
- Mongo write errors now fail the batch instead of being swallowed; writes are idempotent.
- Single streaming query (v1 had 3 queries, one sharing the root checkpoint path with the others).
- Model server no longer depends on MLflow; fake A/B-test code removed.
- Drift detector uses real PSI on live data (v1 compared the test set with itself).
- Grafana dashboard now has real panels and a working provisioning path (v1 had an empty dashboard).
- ELK stack and the 3-broker Kafka cluster were dropped to keep the project light and runnable on a laptop.
- Spark runs from a single custom image (Python 3.11 + Java 17) instead of the deprecated Bitnami image.
