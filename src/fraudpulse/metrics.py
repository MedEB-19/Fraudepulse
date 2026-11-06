"""Prometheus metrics pushed to a Pushgateway after every micro-batch.

Spark's driver is a short-lived/batch-style process, so we PUSH instead of being scraped.
Metrics failures never break the pipeline.
"""
import logging

logger = logging.getLogger("fraudpulse.metrics")


class PipelineMetrics:
    def __init__(self, gateway: str, job: str = "fraudpulse-stream"):
        self.gateway, self.job, self._fail = gateway, job, 0
        self.enabled = bool(gateway)
        if not self.enabled:
            return
        from prometheus_client import CollectorRegistry, Counter, Gauge
        self.registry = CollectorRegistry()
        self.records = Counter("fraudpulse_stream_records_total", "Valid records scored", registry=self.registry)
        self.flagged = Counter("fraudpulse_stream_flagged_total", "Records flagged as fraud", registry=self.registry)
        self.high = Counter("fraudpulse_stream_high_risk_total", "HIGH risk records", registry=self.registry)
        self.invalid = Counter("fraudpulse_stream_invalid_total", "Malformed records sent to DLQ", registry=self.registry)
        self.batches = Counter("fraudpulse_stream_batches_total", "Micro-batches processed", registry=self.registry)
        self.batch_size = Gauge("fraudpulse_stream_batch_size", "Rows in last micro-batch", registry=self.registry)
        self.duration = Gauge("fraudpulse_stream_batch_duration_seconds", "Last micro-batch duration", registry=self.registry)

    def record_batch(self, valid: int, invalid: int, flagged: int, high: int, seconds: float) -> None:
        if not self.enabled:
            return
        self.records.inc(valid); self.invalid.inc(invalid)
        self.flagged.inc(flagged); self.high.inc(high); self.batches.inc()
        self.batch_size.set(valid + invalid); self.duration.set(seconds)
        try:
            from prometheus_client import push_to_gateway
            push_to_gateway(self.gateway, job=self.job, registry=self.registry, timeout=3)
        except Exception as exc:  # noqa: BLE001
            self._fail += 1
            if self._fail == 1 or self._fail % 50 == 0:
                logger.warning("Pushgateway unreachable (%s) - metrics skipped", exc)
