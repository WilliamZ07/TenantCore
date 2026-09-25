import time
import uuid
from dataclasses import dataclass
from redis.asyncio import Redis

# Atomic sliding window script executed inside the Redis engine
# KEYS[1]: Rate limit key (e.g., 'ratelimit:<tenant_id>:api')
# ARGV[1]: Current timestamp in microseconds
# ARGV[2]: Window size in microseconds (e.g., 60_000_000 for 60s)
# ARGV[3]: Maximum allowed requests in window
# ARGV[4]: Unique request identifier
# ARGV[5]: TTL for the key in seconds (cleans up inactive keys)
LUA_SLIDING_WINDOW_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]
local ttl = tonumber(ARGV[5])

local clear_before = now - window

-- 1. Evict entries outside the sliding window
redis.call('ZREMRANGEBYSCORE', key, '-inf', clear_before)

-- 2. Check total requests remaining in current window
local current_requests = redis.call('ZCARD', key)

if current_requests < limit then
    -- 3. Register current request inside the set
    redis.call('ZADD', key, now, member)
    redis.call('EXPIRE', key, ttl)
    return {1, limit - current_requests - 1, 0}
else
    -- 4. Rate limit exceeded: Fetch oldest request timestamp to calculate reset delay
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local reset_delay_us = 0
    if oldest and #oldest > 1 then
        reset_delay_us = (tonumber(oldest[2]) + window) - now
        if reset_delay_us < 0 then
            reset_delay_us = 0
        end
    end
    return {0, 0, math.ceil(reset_delay_us / 1000000)}
end
"""


@dataclass
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_seconds: int


class SlidingWindowRateLimiter:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self._script = self.redis.register_script(LUA_SLIDING_WINDOW_SCRIPT)

    async def check_rate_limit(
        self,
        tenant_id: uuid.UUID,
        action: str = "api",
        limit: int = 100,
        window_seconds: int = 60,
    ) -> RateLimitResult:
        """
        Atomically evaluates rate limit for a tenant over a sliding time window.
        """
        now_us = int(time.time() * 1_000_000)
        window_us = window_seconds * 1_000_000
        key = f"ratelimit:{tenant_id}:{action}"
        member = f"{now_us}:{uuid.uuid4().hex[:8]}"
        ttl_seconds = window_seconds * 2  # Buffer TTL for key cleanup

        result = await self._script(
            keys=[key],
            args=[now_us, window_us, limit, member, ttl_seconds],
        )

        is_allowed = bool(result[0])
        remaining = int(result[1])
        reset_seconds = int(result[2])

        return RateLimitResult(
            allowed=is_allowed,
            limit=limit,
            remaining=remaining,
            reset_seconds=reset_seconds,
        )