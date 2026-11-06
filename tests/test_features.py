import math

from fraudpulse.features import FEATURE_COLS, row_features
from fraudpulse.spark_features import INPUT_SCHEMA, add_features


def test_spark_and_python_features_match(spark, sample_pdf):
    """No train/serve skew: Spark expressions == plain-Python row features."""
    pdf = sample_pdf.head(300)
    sdf = add_features(spark.createDataFrame(pdf, schema=INPUT_SCHEMA))
    rows = sdf.select("step", "type", "amount", "oldbalanceOrg", "newbalanceOrig",
                      "oldbalanceDest", "newbalanceDest", *FEATURE_COLS).collect()
    for r in rows:
        expected = row_features(r.asDict())
        got = [r[c] for c in FEATURE_COLS]
        for e, g in zip(expected, got):
            assert math.isclose(e, g, rel_tol=1e-9, abs_tol=1e-9)


def test_unknown_type_is_minus_one():
    tx = dict(step=5, type="WEIRD", amount=1, oldbalanceOrg=1, newbalanceOrig=0,
              oldbalanceDest=0, newbalanceDest=1)
    assert row_features(tx)[-1] == -1.0
