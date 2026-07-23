"""Metrics for the assistant module.

Labeled counters and histograms for observability (F3).
"""

from motor.observability.metrics_labeled import LabeledCounter, LabeledHistogram

requests_total = LabeledCounter("assistant_requests_total", "Total requests by mode and status")
request_latency = LabeledHistogram("assistant_request_latency_seconds", "Request latency by mode", buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0))
tokens_total = LabeledCounter("assistant_tokens_total", "Tokens generated per provider")
errors_total = LabeledCounter("assistant_errors_total", "Total errors by type and component")
