import logging
import time

import redis

from .config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
log = logging.getLogger("worker")


def main() -> None:
    client = redis.from_url(settings.redis_url, decode_responses=True)
    client.ping()
    log.info("worker started, waiting for jobs (redis=%s)", settings.redis_url)

    # Phase 3 will replace this idle loop with BRPOP on jobs:pending.
    while True:
        time.sleep(30)
        log.info("worker idle heartbeat")


if __name__ == "__main__":
    main()
