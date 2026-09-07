"""
kafka_event_stream.py
---------------------
EventStream interface + optional Kafka adapter (Phase V).

Topics the pipeline would use in production:

    cdr.events          - call-detail-record ingest events
    tips.events         - tip / report ingest events
    transactions.events - transaction ingest events
    pipeline.status     - pipeline stage status transitions

Architecture adapters only: nothing in the demo requires a running broker.
An :class:`InMemoryEventStream` is provided for tests/local wiring.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)

from src.adapters.postgres_repository import AdapterNotConfigured

TOPIC_CDR = "cdr.events"
TOPIC_TIPS = "tips.events"
TOPIC_TRANSACTIONS = "transactions.events"
TOPIC_PIPELINE_STATUS = "pipeline.status"


class EventStream(Protocol):
    def publish(self, topic: str, event: Dict[str, Any]) -> None: ...

    def subscribe(self, topic: str, handler: Callable[[Dict[str, Any]], None]) -> None: ...


class InMemoryEventStream:
    """In-process pub/sub used by tests and the local demo."""

    def __init__(self) -> None:
        self._handlers: Dict[str, List[Callable[[Dict[str, Any]], None]]] = defaultdict(list)
        self._log: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def publish(self, topic: str, event: Dict[str, Any]) -> None:
        envelope = {
            "topic": topic,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "payload": event,
        }
        with self._lock:
            self._log.append(envelope)
        for handler in self._handlers.get(topic, []):
            try:
                handler(event)
            except Exception:  # noqa: BLE001 - subscriber isolation
                logger.exception("event handler failed for topic %s", topic)

    def subscribe(self, topic: str, handler: Callable[[Dict[str, Any]], None]) -> None:
        self._handlers[topic].append(handler)

    def recent(self, topic: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        items = [e for e in self._log if topic is None or e["topic"] == topic]
        return items[-limit:]


class KafkaEventStream:
    """Kafka-backed EventStream (confluent-kafka, lazy import).

    Disabled unless ``SENTINELGRAPH_KAFKA_BOOTSTRAP`` is set.  Import and
    use explicitly; nothing in the demo auto-connects.
    """

    def __init__(self, bootstrap: Optional[str] = None,
                 client_id: str = "sentinelgraph") -> None:
        try:
            from confluent_kafka import Producer  # noqa: F401
        except ImportError as exc:
            raise AdapterNotConfigured(
                "confluent-kafka is not installed. "
                "Install with: pip install confluent-kafka"
            ) from exc
        self.bootstrap = bootstrap or os.environ.get("SENTINELGRAPH_KAFKA_BOOTSTRAP")
        if not self.bootstrap:
            raise AdapterNotConfigured("SENTINELGRAPH_KAFKA_BOOTSTRAP is not set")
        self.client_id = client_id
        self._producer = None

    @property
    def producer(self):
        if self._producer is None:
            from confluent_kafka import Producer

            self._producer = Producer({
                "bootstrap.servers": self.bootstrap,
                "client.id": self.client_id,
            })
        return self._producer

    def publish(self, topic: str, event: Dict[str, Any]) -> None:
        self.producer.produce(topic, json.dumps(event, default=str).encode("utf-8"))
        self.producer.poll(0)

    def subscribe(self, topic: str, handler: Callable[[Dict[str, Any]], None]) -> None:
        logger.warning(
            "KafkaEventStream.subscribe is a no-op placeholder; run a consumer "
            "worker separately (see docs/ARCHITECTURE.md streaming section)."
        )
