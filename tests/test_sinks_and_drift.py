import mongomock
from drift_check import psi
from pyspark.sql import Row

from fraudpulse.sinks import write_partition


def test_mongo_upsert_is_idempotent():
    coll = mongomock.MongoClient().db.transactions
    rows = [Row(kafka_partition=0, kafka_offset=i, amount=10.0 * i) for i in range(5)]
    write_partition(rows, "", "", "", collection=coll)
    write_partition(rows, "", "", "", collection=coll)   # replayed micro-batch
    assert coll.count_documents({}) == 5
    assert coll.find_one({"_id": "0-3"})["amount"] == 30.0


def test_psi_zero_for_same_distribution_and_high_for_shift():
    import numpy as np
    rng = np.random.default_rng(0)
    ref = rng.normal(0, 1, 20000)
    edges = list(np.quantile(ref, np.linspace(0, 1, 11)))
    edges[0], edges[-1] = None, None
    counts, _ = np.histogram(ref, bins=[-np.inf] + edges[1:-1] + [np.inf])
    expected = (counts / counts.sum()).tolist()
    assert psi(expected, rng.normal(0, 1, 20000), edges) < 0.05
    assert psi(expected, rng.normal(2, 1, 20000), edges) > 0.25
