"""Rate limiting middleware using SlowAPI."""

from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.rate_limit_default],
)
