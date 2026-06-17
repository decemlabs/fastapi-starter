# Messaging

Extension point for event/message publishing and consumption (e.g. Redis
Streams, RabbitMQ via FastStream, or Kafka).

**Pattern to follow:**

1. Declare an `EventPublisher` port in the application layer:

   ```python
   class EventPublisher(Protocol):
       async def publish(self, topic: str, payload: Mapping[str, Any]) -> None: ...
   ```

2. Implement the broker adapter here.
3. Provide it via Dishka. Aggregate roots already collect domain events
   (`AggregateRoot.pull_events`); dispatch them from the application layer after
   a successful `commit()` (transactional outbox recommended for at-least-once).

> For real-time delivery to clients, prefer SSE/WebSocket over polling.
