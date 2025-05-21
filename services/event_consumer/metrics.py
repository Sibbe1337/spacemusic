# services/event_consumer/metrics.py
from prometheus_client import Counter, Histogram, start_http_server
import os

KAFKA_MESSAGES_CONSUMED_TOTAL = Counter(
    "event_consumer_kafka_messages_consumed_total",
    "Total Kafka messages consumed by event_consumer.",
    ["topic", "consumer_group", "status"] # status: e.g., success, error_deserialize, error_processing
)

KAFKA_MESSAGE_PROCESSING_DURATION_SECONDS = Histogram(
    "event_consumer_kafka_message_processing_duration_seconds",
    "Duration of processing individual Kafka messages.",
    ["topic", "consumer_group"]
)

APP_ERRORS_TOTAL = Counter(
    "event_consumer_app_errors_total",
    "Total application errors in event_consumer.",
    ["error_type", "component"]
)

def start_metrics_server(port: int = 8004, addr: str = '0.0.0.0'): # Different default port
    metrics_port = int(os.getenv("EVENT_CONSUMER_METRICS_PORT", str(port)))
    try:
        start_http_server(metrics_port, addr=addr)
        print(f"Event Consumer Prometheus metrics server started on port {metrics_port}")
    except OSError as e:
        print(f"Event Consumer Prometheus metrics server failed to start on port {metrics_port}: {e}") 