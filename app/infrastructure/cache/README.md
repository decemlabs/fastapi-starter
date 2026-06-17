# Cache

Extension point for a cache adapter (e.g. Redis via `redis.asyncio`).

**Pattern to follow** (mirrors the rest of the project):

1. Declare the port where it is *used* — an application interface, e.g.
   `app/application/shared/interfaces.py`:

   ```python
   class Cache(Protocol):
       async def get(self, key: str) -> bytes | None: ...
       async def set(self, key: str, value: bytes, ttl_seconds: int) -> None: ...
       async def delete(self, key: str) -> None: ...
   ```

2. Implement it here, e.g. `redis_cache.py` (`RedisCache(redis.Redis)`).
3. Wire it in a Dishka provider (`app/ioc/providers/`) at `Scope.APP`, reading
   `settings.redis.url`.

Keeping the cache behind a port means use cases stay testable with an in-memory
fake and never import Redis directly.
