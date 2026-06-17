# Storage

Extension point for object/file storage (e.g. S3, GCS, local filesystem).

**Pattern to follow:**

1. Declare a `FileStorage` port in the application layer:

   ```python
   class FileStorage(Protocol):
       async def put(self, key: str, data: bytes, content_type: str) -> str: ...
       async def get(self, key: str) -> bytes: ...
       async def delete(self, key: str) -> None: ...
   ```

2. Implement the adapter here (e.g. `s3_storage.py` using `aioboto3`). Use async
   clients only — never block the event loop with synchronous file/network I/O.
3. Provide it via Dishka at `Scope.APP`.
