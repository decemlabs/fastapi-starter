# Messaging

Domain events are **live** in this template at minimum viable scale:

- `UserRegistered` (app/domain/users/events.py) is recorded by `User.create`.
- The `EventDispatcher` port (app/application/shared/interfaces.py) is
  implemented by `InProcessEventDispatcher` (in_process.py) and wired in
  `app/ioc/providers/events.py`, where handlers are registered.
- `CreateUserHandler` dispatches `pull_events()` **after** `uow.commit()`.

To react to an event, add a handler next to the existing
`log_user_registered` example and register it in the provider — one line.

## Upgrade path: transactional outbox

In-process dispatch is at-most-once: if the process dies between commit and
dispatch, the event is lost. When a side effect must not be lost (emails,
webhooks, billing), upgrade behind the same port:

1. Add an `outbox` table (id, occurred_at, event_type, payload JSON,
   processed_at) and write rows inside `SqlAlchemyUnitOfWork.commit()` — same
   transaction as the aggregate change.
2. Replace the dispatcher binding with an outbox-writing implementation; call
   sites do not change.
3. Add a worker entrypoint (reuse `create_container(settings)` the way
   `scripts/seed.py` does) that polls unprocessed rows, publishes to your
   broker (Redis Streams, RabbitMQ via FastStream, Kafka), and stamps
   `processed_at`. Run it as a separate compose service.

## Other extension points

- **EmailSender port** — declare in the application layer:

  ```python
  class EmailSender(Protocol):
      async def send(self, to: str, subject: str, body: str) -> None: ...
  ```

  Implement the provider adapter here, register a `UserRegistered` handler
  that enqueues the verification email, and wire both in the composition
  root.
- **Background jobs (taskiq/arq)** — the worker process reuses the Dishka
  container exactly like the outbox worker above; keep handlers in the
  application layer and enqueue from event handlers.

> For real-time delivery to clients, prefer SSE/WebSocket over polling.
