import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)
sys.path.insert(0, os.path.join(SRC, "monitoring"))
# Spark python workers must be able to import fraudpulse too
os.environ["PYTHONPATH"] = SRC + os.pathsep + os.environ.get("PYTHONPATH", "")
os.environ.setdefault("PYSPARK_PYTHON", sys.executable)


@pytest.fixture(scope="session")
def spark():
    from pyspark.sql import SparkSession
    s = (SparkSession.builder.master("local[2]").appName("fraudpulse-tests")
         .config("spark.sql.session.timeZone", "UTC")
         .config("spark.sql.shuffle.partitions", "2")
         .config("spark.ui.enabled", "false")
         .config("spark.driver.memory", "1g")
         .config("spark.driver.extraJavaOptions", "-Dio.netty.tryReflectionSetAccessible=true")
         .config("spark.executor.extraJavaOptions", "-Dio.netty.tryReflectionSetAccessible=true")
         .getOrCreate())
    s.sparkContext.setLogLevel("ERROR")
    yield s
    s.stop()


@pytest.fixture(scope="session")
def sample_pdf():
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from make_sample_data import generate
    return generate(6000, fraud_rate=0.03, seed=11)
