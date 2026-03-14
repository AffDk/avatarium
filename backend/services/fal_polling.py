"""Shared fal.ai polling helper with exponential backoff.

Replaces subscribe_async() to avoid the hardcoded 100ms polling interval
that floods logs and hammers fal.ai's queue endpoint (~10 requests/second).

Uses submit() + manual status polling with configurable backoff.
"""

import asyncio
import logging
import time

try:
    import fal_client
    from fal_client.client import Completed, InProgress, Queued
except ImportError:
    fal_client = None  # type: ignore[assignment]
    Completed = InProgress = Queued = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

# Polling backoff parameters
INITIAL_POLL_INTERVAL = 2.0   # seconds — first poll after 2s
MAX_POLL_INTERVAL = 15.0      # seconds — cap polling at 15s
BACKOFF_FACTOR = 1.5          # multiply interval by this each iteration


async def submit_and_poll(
    application: str,
    arguments: dict,
    *,
    timeout: float,
    label: str = "fal.ai",
) -> dict:
    """Submit a fal.ai request and poll for completion with exponential backoff.

    Args:
        application: fal.ai application ID (e.g. "fal-ai/qwen-image").
        arguments: JSON-serialisable arguments for the fal.ai model.
        timeout: Maximum total wall-clock seconds to wait.
        label: Human-readable label for log messages (e.g. "image", "video").

    Returns:
        The completed result dict from fal.ai.

    Raises:
        RuntimeError: On timeout or fal.ai error.
    """
    logger.info("[%s] Submitting to %s (timeout=%ds)", label, application, timeout)

    try:
        handle = await fal_client.submit_async(
            application,
            arguments=arguments,
        )
    except Exception as exc:
        logger.error("[%s] Submit failed: %s", label, exc)
        raise RuntimeError(f"{label} submit failed: {exc}") from exc

    request_id = handle.request_id
    logger.info("[%s] Enqueued — request_id=%s", label, request_id)

    # ── Poll with exponential backoff ───────────────────────────────────
    interval = INITIAL_POLL_INTERVAL
    start = time.monotonic()
    last_status_name: str | None = None

    while True:
        elapsed = time.monotonic() - start
        if elapsed >= timeout:
            # Try to cancel the request on the server side
            try:
                await handle.cancel()
            except Exception:
                pass
            logger.error(
                "[%s] Timed out after %.0fs (request_id=%s)",
                label, elapsed, request_id,
            )
            raise RuntimeError(
                f"{label} generation timed out after {int(elapsed)}s "
                f"(request_id={request_id})"
            )

        await asyncio.sleep(interval)

        try:
            status = await handle.status()
        except Exception as exc:
            logger.warning("[%s] Status poll error (will retry): %s", label, exc)
            interval = min(interval * BACKOFF_FACTOR, MAX_POLL_INTERVAL)
            continue

        status_name = type(status).__name__

        # Log on status change with human-friendly descriptions
        if status_name != last_status_name:
            phase = {
                "Queued": "waiting in fal.ai queue",
                "InProgress": "rendering on GPU",
                "Completed": "done",
            }.get(status_name, status_name)
            logger.info(
                "[%s] %s (%.0fs elapsed)",
                label, phase, time.monotonic() - start,
            )
            last_status_name = status_name

        if isinstance(status, Completed):
            break

        # Increase interval (backoff), but reset to a shorter interval
        # when the status changes to InProgress (processing has started).
        if isinstance(status, InProgress) and interval > INITIAL_POLL_INTERVAL:
            interval = INITIAL_POLL_INTERVAL
        else:
            interval = min(interval * BACKOFF_FACTOR, MAX_POLL_INTERVAL)

    # ── Fetch the completed result ──────────────────────────────────────
    logger.info("[%s] Completed — downloading result...", label)
    try:
        result = await handle.get()
    except Exception as exc:
        logger.error("[%s] Failed to fetch result: %s", label, exc)
        raise RuntimeError(f"{label} result retrieval failed: {exc}") from exc

    elapsed = time.monotonic() - start
    logger.info("[%s] Finished in %.1fs", label, elapsed)
    return result
