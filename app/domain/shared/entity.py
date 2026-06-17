"""Building blocks for domain entities and aggregate roots (DDD tactical patterns).

``Entity`` and ``AggregateRoot`` are generic over the identity type ``IdT`` so
that ``identity()`` is fully typed per aggregate (no ``Any``).
"""

from dataclasses import dataclass, field

from app.domain.shared.events import DomainEvent


def _new_events() -> list[DomainEvent]:
    return []


@dataclass(eq=False)
class Entity[IdT]:
    """An object defined by its identity rather than by its attributes.

    Equality and hashing are based on identity, so two instances representing
    the same conceptual entity compare equal even if some attributes differ.
    Subclasses must override :meth:`identity`.
    """

    def identity(self) -> IdT:
        raise NotImplementedError

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            return NotImplemented
        return bool(self.identity() == other.identity())

    def __hash__(self) -> int:
        return hash((type(self).__name__, self.identity()))


@dataclass(eq=False)
class AggregateRoot[IdT](Entity[IdT]):
    """An entity that is the entry point to a consistency boundary.

    Aggregate roots are the only objects repositories load and persist.
    """

    _events: list[DomainEvent] = field(
        default_factory=_new_events, init=False, repr=False
    )

    def record_event(self, event: DomainEvent) -> None:
        self._events.append(event)

    def pull_events(self) -> list[DomainEvent]:
        events = self._events
        self._events = []
        return events
