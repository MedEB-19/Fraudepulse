"""End-to-end (local Spark): train XGBoost inside Spark -> save -> load -> score a
micro-batch with the exact code used by the streaming job."""
import json

import numpy as np
import xgboost as xgb
from pyspark.sql import functions as F
from xgboost.spark import SparkXGBClassifier, SparkXGBClassifierModel

from fraudpulse.features import FEATURE_COLS, row_features
from fraudpulse.scoring import score_dataframe
from fraudpulse.spark_features import INPUT_SCHEMA, add_features, with_feature_vector
from jobs.stream import split_valid_invalid


def _train(spark, pdf, tmp_path):
    df = add_features(spark.createDataFrame(pdf, schema=INPUT_SCHEMA)).select(*FEATURE_COLS, "isFraud")
    df = with_feature_vector(df)
    pos = df.filter("isFraud = 1").count()
    clf = SparkXGBClassifier(features_col="features", label_col="isFraud", num_workers=2,
                             n_estimators=30, max_depth=4, scale_pos_weight=(df.count() - pos) / pos,
                             tree_method="hist", random_state=1)
    model = clf.fit(df)
    path = (tmp_path / "spark_model").resolve().as_uri()
    model.write().overwrite().save(path)
    return SparkXGBClassifierModel.load(path), model


def test_train_save_load_score(spark, sample_pdf, tmp_path):
    loaded, trained = _train(spark, sample_pdf, tmp_path)

    # simulate a Kafka micro-batch: partition / offset / value(JSON bytes)
    good = sample_pdf.head(200)
    msgs = [json.dumps({k: (v.item() if hasattr(v, "item") else v) for k, v in r.items()}) for r in good.to_dict("records")]
    msgs += ["not-json-at-all", json.dumps({"step": 1, "type": "PAYMENT"})]     # 2 malformed
    batch = spark.createDataFrame([(0, i, m.encode()) for i, m in enumerate(msgs)],
                                  "partition int, offset long, value binary")
    valid, invalid = split_valid_invalid(batch)
    assert valid.count() == 200 and invalid.count() == 2

    scored = score_dataframe(valid, loaded, 0.5, 200000.0)
    out = scored.toPandas()
    assert len(out) == 200
    assert out["fraud_probability"].between(0, 1).all()
    assert set(out["risk_level"]) <= {"LOW", "MEDIUM", "HIGH"}
    assert out["fraud_flag"].dtype == bool
    # fraud rows should on average score higher than legit rows
    assert out.loc[out.isFraud == 1, "fraud_probability"].mean() > out.loc[out.isFraud == 0, "fraud_probability"].mean()


def test_exported_booster_matches_spark(spark, sample_pdf, tmp_path):
    """The REST server (plain xgboost) must give the same probability as the Spark model."""
    loaded, trained = _train(spark, sample_pdf, tmp_path)
    path = tmp_path / "fraud_model.json"
    trained.get_booster().save_model(str(path))
    booster = xgb.Booster(); booster.load_model(str(path))

    rows = sample_pdf.head(20)
    spark_p = (score_dataframe(spark.createDataFrame(rows, schema=INPUT_SCHEMA).withColumn("x", F.lit(0)).drop("x"),
                               loaded, 0.5, 200000.0)
               .select("nameOrig", "step", "amount", "fraud_probability").toPandas())
    feats = np.array([row_features(r) for r in rows.to_dict("records")], dtype=np.float32)
    py_p = booster.predict(xgb.DMatrix(feats))
    merged = rows.reset_index(drop=True).assign(py=py_p).merge(spark_p, on=["nameOrig", "step", "amount"])
    assert np.allclose(merged["py"], merged["fraud_probability"], atol=1e-4)
