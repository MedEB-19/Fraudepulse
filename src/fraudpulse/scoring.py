"""Scoring = XGBoost (inside Spark) + business rule + risk level."""
from pyspark.ml.functions import vector_to_array
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from fraudpulse.spark_features import add_features, with_feature_vector

RULE_TEXT = "Large transfer/cash-out that empties the origin account and leaves destination unchanged."


def apply_decisions(df: DataFrame, threshold: float, rule_amount: float) -> DataFrame:
    """Expects columns: fraud_probability + raw transaction columns + features."""
    rule = (
        F.col("type").isin("TRANSFER", "CASH_OUT")
        & (F.col("newbalanceOrig") == 0)
        & (F.col("newbalanceDest") == F.col("oldbalanceDest"))
        & (F.col("amount") > F.lit(rule_amount))
    )
    return (
        df
        .withColumn("model_flag", F.col("fraud_probability") > F.lit(threshold))
        .withColumn("rule_engine_flag", rule)
        .withColumn("rule_triggered",
                    F.when(F.col("rule_engine_flag"), F.lit(RULE_TEXT)).otherwise(F.lit("None")))
        .withColumn("fraud_flag", F.col("model_flag") | F.col("rule_engine_flag"))
        .withColumn("risk_level",
                    F.when((F.col("fraud_probability") > 0.8) | F.col("rule_engine_flag"), F.lit("HIGH"))
                     .when(F.col("fraud_probability") > F.lit(threshold), F.lit("MEDIUM"))
                     .otherwise(F.lit("LOW")))
        .withColumn("processed_at", F.current_timestamp())
        # binary features -> booleans for readable documents / dashboard
        .withColumn("balance_drained", F.col("balance_drained") == 1.0)
        .withColumn("dest_balance_unchanged", F.col("dest_balance_unchanged") == 1.0)
        .withColumn("is_transfer_or_cashout", F.col("is_transfer_or_cashout") == 1.0)
    )


def score_dataframe(df: DataFrame, model, threshold: float, rule_amount: float) -> DataFrame:
    """Run the Spark-native XGBoost model on a (batch / micro-batch) DataFrame."""
    featured = with_feature_vector(add_features(df))
    scored = model.transform(featured)  # SparkXGBClassifierModel: distributed inference
    scored = (
        scored
        .withColumn("fraud_probability", vector_to_array(F.col("probability"))[1])
        .drop("rawPrediction", "probability", "prediction", "features")
    )
    return apply_decisions(scored, threshold, rule_amount)
