"""Feature definitions (pure Python, no Spark dependency).

The SAME definitions are used by:
  * the Spark training job        (add_features on a batch DataFrame)
  * the Spark streaming job       (add_features on each micro-batch)
  * the FastAPI model server      (row_features on one transaction)

Sharing one module removes train/serve skew (the original project hard-coded the
type mapping in several places).
"""
from typing import Dict

# Fixed mapping -> deterministic across runs (unknown types become -1).
TYPE_MAPPING: Dict[str, int] = {
    "PAYMENT": 0, "TRANSFER": 1, "CASH_OUT": 2, "DEBIT": 3, "CASH_IN": 4,
}

FEATURE_COLS = [
    "amount", "oldbalanceOrg", "newbalanceOrig", "oldbalanceDest", "newbalanceDest",
    "balance_drained", "dest_balance_unchanged", "amount_to_balance_ratio",
    "hour_of_day", "is_transfer_or_cashout", "type_encoded",
]

# Raw columns that must be present (non-null) for a record to be scorable.
REQUIRED_COLS = [
    "step", "type", "amount", "oldbalanceOrg", "newbalanceOrig",
    "oldbalanceDest", "newbalanceDest",
]


def row_features(tx: dict) -> list:
    """Same features for ONE transaction (plain Python) -> list in FEATURE_COLS order."""
    amount = float(tx["amount"])
    old_org, new_org = float(tx["oldbalanceOrg"]), float(tx["newbalanceOrig"])
    old_dst, new_dst = float(tx["oldbalanceDest"]), float(tx["newbalanceDest"])
    return [
        amount, old_org, new_org, old_dst, new_dst,
        1.0 if new_org == 0 else 0.0,
        1.0 if new_dst == old_dst else 0.0,
        amount / (old_org + 1.0),
        float(int(tx["step"]) % 24),
        1.0 if tx["type"] in ("TRANSFER", "CASH_OUT") else 0.0,
        float(TYPE_MAPPING.get(tx["type"], -1)),
    ]
