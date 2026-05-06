"""Tenacity retry decorator scoped to retriable AWS errors.

The job_handler retry loop already covers transient errors at the job
grain (3 attempts with backoff). This decorator adds in-client retries
inside a single Bedrock/Comprehend call so a single throttle doesn't
burn a whole job-level attempt.

Only retries on:
  - boto3 ClientError with code in _RETRIABLE_CODES (throttling, server
    errors, transient unavailability)
  - boto3 BotoCoreError (network/connection issues — by definition
    transient)

Does NOT retry on:
  - AccessDeniedException, ValidationException, ResourceNotFoundException,
    or any other "your request is wrong" 4xx — retrying won't help
"""

from __future__ import annotations

import logging

from botocore.exceptions import BotoCoreError, ClientError
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

log = logging.getLogger(__name__)


_RETRIABLE_CODES = frozenset({
    "ThrottlingException",
    "TooManyRequestsException",
    "ServiceUnavailableException",
    "RequestLimitExceeded",
    "InternalServerException",
    "ModelTimeoutException",
    "ModelStreamErrorException",
    "ModelNotReadyException",
    "ProvisionedThroughputExceededException",
})


def _is_retriable(exc: BaseException) -> bool:
    if isinstance(exc, ClientError):
        return exc.response.get("Error", {}).get("Code", "") in _RETRIABLE_CODES
    if isinstance(exc, BotoCoreError):
        # Connection/socket-level errors. boto3 has its own retries via Config
        # but they aren't always sufficient under sustained throttle.
        return True
    return False


def aws_retry(attempts: int = 3, max_wait_s: float = 10.0):
    """Tenacity decorator factory tuned for AWS retriable errors.

    Defaults to 3 attempts, exponential backoff capped at 10s.
    Re-raises the final exception so callers see it normally.
    """
    return retry(
        stop=stop_after_attempt(attempts),
        wait=wait_exponential(multiplier=1, min=1, max=max_wait_s),
        retry=retry_if_exception(_is_retriable),
        reraise=True,
        before_sleep=before_sleep_log(log, logging.WARNING),
    )
