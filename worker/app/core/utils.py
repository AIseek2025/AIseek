"""
Utility Functions (Refactored from Fusion)
"""

import asyncio
import time
import logging
from typing import Callable, TypeVar, Any

logger = logging.getLogger(__name__)

T = TypeVar("T")

def retry_sync(
    func: Callable[[], T],
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0
) -> T:
    """Synchronous retry with exponential backoff."""
    last_exc = None
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_exc = e
            if attempt == max_retries - 1:
                logger.error(f"Retry failed after {max_retries} attempts: {e}")
                raise
            sleep_time = delay * (backoff_factor ** attempt)
            logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {sleep_time}s...")
            time.sleep(sleep_time)
    raise last_exc

async def retry_async(
    func: Callable[[], Any],
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0
) -> Any:
    """Asynchronous retry with exponential backoff."""
    last_exc = None
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            last_exc = e
            if attempt == max_retries - 1:
                logger.error(f"Async retry failed after {max_retries} attempts: {e}")
                raise
            sleep_time = delay * (backoff_factor ** attempt)
            logger.warning(f"Async attempt {attempt + 1} failed: {e}. Retrying in {sleep_time}s...")
            await asyncio.sleep(sleep_time)
    raise last_exc
