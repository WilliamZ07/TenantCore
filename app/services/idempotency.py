import json
import uuid
from typing import Any
from redis.asyncio import Redis


class IdempotencyService:
    def __init__(self, redis: Redis):
        self.redis = redis

    def _format_key(self, tenant_id: uuid.UUID, idempotency_key: str) -> str:
        return f"idempotency:{tenant_id}:{idempotency_key.strip()}"

    async def get_cached_response(
        self, tenant_id: uuid.UUID, idempotency_key: str
    ) -> dict[str, Any] | None:
        """
        Retrieves cached response if the idempotency key was previously processed.
        """
        key = self._format_key(tenant_id, idempotency_key)
        cached = await self.redis.get(key)
        if cached:
            return json.loads(cached)
        return None

    async def lock_key(
        self, tenant_id: uuid.UUID, idempotency_key: str, ttl_seconds: int = 120
    ) -> bool:
        """
        Attempts to acquire an atomic processing lock for this idempotency key.
        Returns True if acquired, False if another request is currently in-flight.
        """
        key = self._format_key(tenant_id, idempotency_key)
        payload = json.dumps({"status": "processing"})
        # SET NX: Only sets key if it does not already exist
        acquired = await self.redis.set(key, payload, ex=ttl_seconds, nx=True)
        return bool(acquired)

    async def store_response(
        self,
        tenant_id: uuid.UUID,
        idempotency_key: str,
        status_code: int,
        response_body: dict[str, Any],
        ttl_seconds: int = 86400,  # 24-hour persistence
    ) -> None:
        """
        Stores finalized HTTP response payload against the idempotency key.
        """
        key = self._format_key(tenant_id, idempotency_key)
        payload = json.dumps({
            "status": "completed",
            "status_code": status_code,
            "body": response_body,
        })
        await self.redis.set(key, payload, ex=ttl_seconds)