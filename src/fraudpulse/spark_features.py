"""Spark side of the feature engineering (same formulas as features.row_features)."""
from itertools import chain

from pyspark.ml.functions import array_to_vector
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, IntegerType, StringType, StructField, StructType

from fraudpulse.features import FEATURE_COLS, TYPE_MAPPING

# Schema of the PaySim CSV *and* of the JSON messages on the Kafka topic.
INPUT_SCHEMA = StructType([
    StructField("step", IntegerType(), True),
    StructField("type", StringType(), True),
    StructField("amount", DoubleType(), True),
    StructField("nameOrig", StringType(), True),
    StructField("oldbalanceOrg", DoubleType(), True),
    StructField("newbalanceOrig", DoubleType(), True),
    StructField("nameDest", StringType(), True),
    StructField("oldbalanceDest", DoubleType(), True),
    StructField("newbalanceDest", DoubleType(), True),
    StructField("isFraud", IntegerType(), True),
    StructField("isFlaggedFraud", IntegerType(), True),
])


def add_features(df: DataFrame) -> DataFrame:
    """Add the 6 engineered features (Spark SQL expressions, no Python UDF)."""
    type_map = F.create_map(
        *chain.from_iterable((F.lit(k), F.lit(v)) for k, v in TYPE_MAPPING.items())
    )
    return (
        df
        .withColumn("balance_drained",
                    F.when(F.col("newbalanceOrig") == 0, 1.0).otherwise(0.0))
        .withColumn("dest_balance_unchanged",
                    F.when(F.col("newbalanceDest") == F.col("oldbalanceDest"), 1.0).otherwise(0.0))
        .withColumn("amount_to_balance_ratio",
                    F.col("amount") / (F.col("oldbalanceOrg") + F.lit(1.0)))
        .withColumn("hour_of_day", (F.col("step") % 24).cast("double"))
        .withColumn("is_transfer_or_cashout",
                    F.when(F.col("type").isin("TRANSFER", "CASH_OUT"), 1.0).otherwise(0.0))
        .withColumn("type_encoded",
                    F.coalesce(type_map[F.col("type")], F.lit(-1)).cast("double"))
    )


def with_feature_vector(df: DataFrame) -> DataFrame:
    """Pack FEATURE_COLS into ONE dense `features` vector column.

    xgboost.spark (CPU) requires a single vector column. We build a DENSE vector on purpose:
    with sparse vectors, zeros could be mistaken for missing values.
    """
    return df.withColumn(
        "features", array_to_vector(F.array(*[F.col(c).cast("double") for c in FEATURE_COLS])))
