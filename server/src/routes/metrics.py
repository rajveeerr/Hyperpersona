"""Operational metrics — exposed publicly (no rate limit) so operators can
always see system load even when the system itself is overloaded.
"""

from fastapi import APIRouter

from shared.constants import QUEUE_PENDING

from ..config import settings
from ..deps import redis_client


router = APIRouter()


@router.get("/metrics/queue")
def queue_metrics() -> dict:
    """Current worker queue depth and how close we are to the backpressure cap."""
    depth = int(redis_client.llen(QUEUE_PENDING))
    cap = settings.max_queue_depth
    return {
        "queue_depth": depth,
        "max_queue_depth": cap,
        "load_pct": round(100 * depth / cap, 1) if cap else 0.0,
    }
