from collections.abc import Awaitable, Callable
from functools import wraps
from time import perf_counter
from typing import Any

from loguru import logger


def elapsed_minutes(started_at: float) -> float:
    return round((perf_counter() - started_at) / 60, 4)


def log_async_timing(label: str | None = None) -> Callable:
    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        timing_label = label or func.__qualname__

        @wraps(func)
        async def wrapper(*args, **kwargs):
            started_at = perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                logger.info(
                    "Function timing | name={} | duration_min={}",
                    timing_label,
                    elapsed_minutes(started_at),
                )

        return wrapper

    return decorator
