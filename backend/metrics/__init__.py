"""
Metrics collection module for Prometheus monitoring.

Bu modül sistemin performansını ölçmek için kullanılır.
Prometheus ile entegre çalışır.
"""
from .prometheus_exporter import (
    # Metrics
    message_generation_total,
    message_generation_duration_seconds,
    active_bots_gauge,
    database_query_duration_seconds,
    database_connections_gauge,
    telegram_api_calls_total,
    llm_api_calls_total,
    llm_token_usage_total,
    http_requests_total,
    http_request_duration_seconds,

    # Middleware
    PrometheusMiddleware,

    # Functions
    setup_metrics,
)

__all__ = [
    # Metrics
    "message_generation_total",
    "message_generation_duration_seconds",
    "active_bots_gauge",
    "database_query_duration_seconds",
    "database_connections_gauge",
    "telegram_api_calls_total",
    "llm_api_calls_total",
    "llm_token_usage_total",
    "http_requests_total",
    "http_request_duration_seconds",

    # Middleware
    "PrometheusMiddleware",

    # Functions
    "setup_metrics",
]
