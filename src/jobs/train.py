"""Distributed XGBoost training INSIDE Spark (xgboost.spark.SparkXGBClassifier).

Pipeline: CSV -> Spark feature engineering -> train/test split -> distributed XGBoost
-> evaluation -> save (1) Spark ML model for the streaming job, (2) plain booster JSON
for the REST server, (3) metrics + reference statistics (for drift monitoring).
"""
import argparse
import json
import logging
import os
from pathlib import Path

import numpy as np
from pyspark.ml.evaluation import BinaryClassificationEvaluator
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from xgboost.spark import SparkXGBClassifier

from fraudpulse.features import FEATURE_COLS
from fraudpulse.spark_features import INPUT_SCHEMA, add_features, with_feature_vector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s - %(message)s")
log = logging.getLogger("fraudpulse.train")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--data", default=os.environ.get("DATA_PATH", "/app/data/paysim.csv"))
    p.add_argument("--model-dir", default=os.environ.get("MODEL_DIR", "/app/models"))
    p.add_argument("--num-workers", type=int, default=int(os.environ.get("XGB_NUM_WORKERS", "2")))
    p.add_argument("--sample-fraction", type=float, default=float(os.environ.get("TRAIN_SAMPLE_FRACTION", "1.0")))
    p.add_argument("--n-estimators", type=int, default=100)
    p.add_argument("--max-depth", type=int, default=6)
    p.add_argument("--learning-rate", type=float, default=0.1)
    p.add_argument("--threshold", type=float, default=float(os.environ.get("FRAUD_THRESHOLD", "0.5")))
    return p.parse_args()


def evaluate(model, test_df, threshold: float) -> dict:
    pred = model.transform(test_df).cache()
    out = {}
    for name, metric in (("auc_roc", "areaUnderROC"), ("auc_pr", "areaUnderPR")):
        out[name] = BinaryClassificationEvaluator(
            rawPredictionCol="probability", labelCol="isFraud", metricName=metric).evaluate(pred)

    from pyspark.ml.functions import vector_to_array
    p = vector_to_array("probability")[1]
    y = F.col("isFraud")
    c = pred.agg(
        F.sum(F.when((p >= threshold) & (y == 1), 1).otherwise(0)).alias("tp"),
        F.sum(F.when((p >= threshold) & (y == 0), 1).otherwise(0)).alias("fp"),
        F.sum(F.when((p < threshold) & (y == 1), 1).otherwise(0)).alias("fn"),
        F.sum(F.when((p < threshold) & (y == 0), 1).otherwise(0)).alias("tn"),
    ).first().asDict()
    tp, fp, fn = c["tp"] or 0, c["fp"] or 0, c["fn"] or 0
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    out.update(precision=prec, recall=rec,
               f1=(2 * prec * rec / (prec + rec)) if prec + rec else 0.0,
               threshold=threshold, **{k: int(v or 0) for k, v in c.items()})
    pred.unpersist()
    return out


def reference_stats(train_df, max_rows: int = 200_000) -> dict:
    """Bin edges + expected proportions per feature (used by the PSI drift check)."""
    total = train_df.count()
    frac = min(1.0, max_rows / max(total, 1))
    pdf = train_df.select(*FEATURE_COLS).sample(False, frac, seed=1).toPandas()
    stats = {}
    for col in FEATURE_COLS:
        edges = np.unique(np.quantile(pdf[col], np.linspace(0, 1, 11)))
        if len(edges) < 2:
            continue
        edges[0], edges[-1] = -np.inf, np.inf
        counts, _ = np.histogram(pdf[col], bins=edges)
        stats[col] = {"edges": [None if np.isinf(e) else float(e) for e in edges],
                      "expected": (counts / counts.sum()).tolist()}
    return stats


def main():
    a = parse_args()
    model_dir = Path(a.model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    spark = (SparkSession.builder.appName("FraudPulseTrain")
             .config("spark.sql.session.timeZone", "UTC").getOrCreate())
    spark.sparkContext.setLogLevel("WARN")

    log.info("Reading %s", a.data)
    raw = spark.read.csv(a.data, header=True, schema=INPUT_SCHEMA)
    df = add_features(raw).select(*FEATURE_COLS, "isFraud").dropna()
    df = with_feature_vector(df)
    if a.sample_fraction < 1.0:
        df = df.sample(False, a.sample_fraction, seed=42)

    train, test = df.randomSplit([0.8, 0.2], seed=42)
    train, test = train.cache(), test.cache()
    counts = {r["isFraud"]: r["count"] for r in train.groupBy("isFraud").count().collect()}
    pos, neg = counts.get(1, 0), counts.get(0, 0)
    if pos == 0:
        raise SystemExit("No fraud rows in the training split - check the dataset.")
    spw = neg / pos
    log.info("Train rows: fraud=%d legit=%d scale_pos_weight=%.1f", pos, neg, spw)

    clf = SparkXGBClassifier(
        features_col="features", label_col="isFraud",
        num_workers=a.num_workers,             # XGBoost workers = Spark barrier tasks
        n_estimators=a.n_estimators, max_depth=a.max_depth, learning_rate=a.learning_rate,
        scale_pos_weight=spw, tree_method="hist", eval_metric="aucpr", random_state=42,
    )
    log.info("Training distributed XGBoost on %d Spark worker(s)...", a.num_workers)
    model = clf.fit(train)

    metrics = evaluate(model, test, a.threshold)
    log.info("Test metrics: %s", json.dumps(metrics))

    spark_model_path = model_dir / "spark_model"
    model.write().overwrite().save(spark_model_path.resolve().as_uri())
    model.get_booster().save_model(str(model_dir / "fraud_model.json"))
    (model_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    (model_dir / "reference_stats.json").write_text(json.dumps(reference_stats(train)))
    (model_dir / "feature_cols.json").write_text(json.dumps(FEATURE_COLS))
    log_to_mlflow(a, metrics, model_dir)
    log.info("Saved model + artifacts to %s", model_dir)
    spark.stop()


def log_to_mlflow(a, metrics: dict, model_dir: Path) -> None:
    """Optional experiment tracking - skipped silently if MLflow is not configured/reachable."""
    uri = os.environ.get("MLFLOW_TRACKING_URI")
    if not uri:
        return
    try:
        import mlflow
        mlflow.set_tracking_uri(uri)
        mlflow.set_experiment(os.environ.get("MLFLOW_EXPERIMENT_NAME", "FraudPulse-XGBoost"))
        with mlflow.start_run(run_name="spark-xgb-training"):
            mlflow.log_params({"n_estimators": a.n_estimators, "max_depth": a.max_depth,
                               "learning_rate": a.learning_rate, "num_workers": a.num_workers})
            mlflow.log_metrics({k: v for k, v in metrics.items() if isinstance(v, float)})
            for f in ("fraud_model.json", "metrics.json", "reference_stats.json"):
                mlflow.log_artifact(str(model_dir / f))
        log.info("Logged run to MLflow at %s", uri)
    except Exception as exc:  # noqa: BLE001
        log.warning("MLflow logging skipped: %s", exc)


if __name__ == "__main__":
    main()
