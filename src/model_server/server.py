"""FastAPI REST scoring endpoint using the SAME XGBoost model Spark trained.

POST /predict  -> fraud probability for one transaction (uses fraudpulse.features.row_features)
"""
import logging
import os
import threading

import numpy as np
import xgboost as xgb
from fastapi import FastAPI, HTTPException
from prometheus_client import Counter, Histogram, make_asgi_app
from schemas import PredictionResponse, TransactionSchema

from fraudpulse.features import row_features

log = logging.getLogger("fraudpulse.model_server")
MODEL_PATH = os.environ.get("MODEL_PATH", "/app/models/fraud_model.json")
THRESHOLD = float(os.environ.get("FRAUD_THRESHOLD", "0.5"))

app = FastAPI(title="FraudPulse Model Server", version="2.0.0")
app.mount("/metrics", make_asgi_app())
REQS = Counter("model_prediction_requests_total", "Prediction requests")
LAT = Histogram("model_prediction_latency_seconds", "Prediction latency")

_booster, _mtime, _lock = None, None, threading.Lock()


def get_booster():
    """Lazy-load and hot-reload when training writes a new model file."""
    global _booster, _mtime
    if not os.path.exists(MODEL_PATH):
        return None
    mtime = os.path.getmtime(MODEL_PATH)
    if _booster is None or mtime != _mtime:
        with _lock:
            b = xgb.Booster()
            b.load_model(MODEL_PATH)
            _booster, _mtime = b, mtime
            log.info("Loaded model %s", MODEL_PATH)
    return _booster


@app.post("/predict", response_model=PredictionResponse)
def predict(tx: TransactionSchema):
    booster = get_booster()
    if booster is None:
        raise HTTPException(status_code=503, detail="Model not trained yet (run `make train`).")
    REQS.inc()
    with LAT.time():
        feats = np.array([row_features(tx.model_dump())], dtype=np.float32)
        prob = float(booster.predict(xgb.DMatrix(feats))[0])
    return PredictionResponse(fraud_probability=prob, is_fraud=prob > THRESHOLD, threshold=THRESHOLD)


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": get_booster() is not None}
