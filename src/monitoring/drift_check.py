"""Data-drift check: Population Stability Index (PSI) between the training distribution
(models/reference_stats.json) and the most recent scored transactions in MongoDB.

PSI < 0.1 stable | 0.1-0.25 moderate drift | > 0.25 significant drift (consider retraining).
"""
import json
import os

import numpy as np

EPS = 1e-6


def psi(expected: list, actual_values, edges: list) -> float:
    e = np.array([-np.inf if x is None and i == 0 else (np.inf if x is None else x)
                  for i, x in enumerate(edges)])
    counts, _ = np.histogram(np.asarray(actual_values, dtype=float), bins=e)
    if counts.sum() == 0:
        return 0.0
    a = np.clip(counts / counts.sum(), EPS, None)
    x = np.clip(np.array(expected), EPS, None)
    return float(np.sum((a - x) * np.log(a / x)))


def run(stats_path: str, uri: str, db: str, coll: str, limit: int = 20000) -> dict:
    from pymongo import MongoClient
    stats = json.load(open(stats_path))
    docs = list(MongoClient(uri)[db][coll].find({}, {c: 1 for c in stats}).sort("processed_at", -1).limit(limit))
    if not docs:
        raise SystemExit("No documents in MongoDB yet.")
    report = {}
    for col, s in stats.items():
        vals = [float(d[col]) for d in docs if col in d]
        report[col] = psi(s["expected"], vals, s["edges"])
    return report


if __name__ == "__main__":
    rep = run(os.environ.get("REFERENCE_STATS", "models/reference_stats.json"),
              os.environ.get("MONGO_URI", "mongodb://localhost:27017/"),
              os.environ.get("MONGO_DB", "fraud_db"), os.environ.get("MONGO_COLLECTION", "transactions"))
    for k, v in sorted(rep.items(), key=lambda kv: -kv[1]):
        flag = "DRIFT" if v > 0.25 else ("watch" if v > 0.1 else "ok")
        print(f"{k:28s} PSI={v:6.3f}  {flag}")
    if max(rep.values()) > 0.25:
        print("\nSignificant drift detected -> retrain with `make train`.")
