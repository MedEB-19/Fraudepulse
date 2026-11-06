from typing import Optional

from pydantic import BaseModel


class TransactionSchema(BaseModel):
    step: int
    type: str
    amount: float
    nameOrig: str = ""
    oldbalanceOrg: float
    newbalanceOrig: float
    nameDest: str = ""
    oldbalanceDest: float
    newbalanceDest: float
    isFraud: Optional[int] = None
    isFlaggedFraud: Optional[int] = None


class PredictionResponse(BaseModel):
    fraud_probability: float
    is_fraud: bool
    threshold: float
