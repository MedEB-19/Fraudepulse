"""Generate a small synthetic PaySim-like CSV (for smoke tests / CI - NOT real data).

Usage: python scripts/make_sample_data.py --rows 50000 --out data/paysim_sample.csv
For the real project, download PaySim from Kaggle (see data/README.md).
"""
import argparse

import numpy as np
import pandas as pd

TYPES = ["PAYMENT", "TRANSFER", "CASH_OUT", "DEBIT", "CASH_IN"]


def generate(rows: int, fraud_rate: float = 0.02, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    t = rng.choice(TYPES, size=rows, p=[0.34, 0.08, 0.35, 0.01, 0.22])
    amount = np.round(rng.lognormal(mean=10.0, sigma=1.4, size=rows), 2)
    old_org = np.round(rng.lognormal(mean=10.5, sigma=2.0, size=rows) * (rng.random(rows) > 0.3), 2)
    old_dst = np.round(rng.lognormal(mean=10.5, sigma=2.0, size=rows) * (rng.random(rows) > 0.4), 2)

    is_fraud = np.zeros(rows, dtype=int)
    eligible = np.isin(t, ["TRANSFER", "CASH_OUT"])
    is_fraud[eligible & (rng.random(rows) < fraud_rate / 0.43)] = 1

    # fraud pattern: account emptied; ~15% of fraud looks "normal" and a few legit rows look suspicious
    amount = np.where(is_fraud == 1, np.round(rng.lognormal(12.0, 1.0, rows), 2), amount)
    old_org = np.where(is_fraud == 1, amount, old_org)
    new_org = np.maximum(old_org - amount, 0.0)
    camouflage = (is_fraud == 1) & (rng.random(rows) < 0.15)
    new_org = np.where(camouflage, old_org * 0.5, new_org)
    legit_drain = (is_fraud == 0) & eligible & (rng.random(rows) < 0.01)
    new_org = np.where(legit_drain, 0.0, new_org)

    new_dst = np.where(t == "CASH_IN", old_dst + amount, old_dst + amount)
    unchanged = (is_fraud == 1) & (rng.random(rows) < 0.8)
    new_dst = np.where(unchanged, old_dst, new_dst)
    new_org = np.where(t == "CASH_IN", old_org + amount, new_org)

    return pd.DataFrame({
        "step": rng.integers(1, 744, rows), "type": t, "amount": amount,
        "nameOrig": [f"C{i:09d}" for i in rng.integers(0, 10**9, rows)],
        "oldbalanceOrg": old_org, "newbalanceOrig": np.round(new_org, 2),
        "nameDest": [f"C{i:09d}" for i in rng.integers(0, 10**9, rows)],
        "oldbalanceDest": old_dst, "newbalanceDest": np.round(new_dst, 2),
        "isFraud": is_fraud, "isFlaggedFraud": 0,
    })


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=50000)
    ap.add_argument("--out", default="data/paysim_sample.csv")
    a = ap.parse_args()
    df = generate(a.rows)
    df.to_csv(a.out, index=False)
    print(f"wrote {len(df)} rows ({df.isFraud.sum()} fraud) -> {a.out}")
