"""Idempotently create the SQS job queue.

Reads SQS_QUEUE_NAME (default: hyperpersona-jobs) + AWS_REGION from env.
Creates the queue if it doesn't exist, prints the URL.

Visibility timeout = 90s — covers Strands ingest at ~17s plus the
3-attempt retry-with-backoff (cumulative ~7s of sleeps). Worst case a
slow job is in flight for ~50s, well under the timeout.

Message retention = 4 days (default) so dead-letter handling has runway.

Usage:
    docker compose exec worker python /app/scripts/setup_sqs.py
or:
    make setup-sqs
"""

import os
import sys

import boto3
from botocore.exceptions import ClientError


def main() -> int:
    queue_name = os.getenv("SQS_QUEUE_NAME", "hyperpersona-jobs").strip()
    region = os.getenv("AWS_REGION", "us-east-1")

    sqs = boto3.client("sqs", region_name=region)

    try:
        existing = sqs.get_queue_url(QueueName=queue_name)
        url = existing["QueueUrl"]
        print(f"queue already exists: {url}")
        print(f"\nadd to .env:\n  QUEUE_MODE=sqs\n  SQS_QUEUE_URL={url}")
        return 0
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code != "AWS.SimpleQueueService.NonExistentQueue":
            print(f"get_queue_url failed: {code}: {e}", file=sys.stderr)
            return 1

    try:
        resp = sqs.create_queue(
            QueueName=queue_name,
            Attributes={
                # Hide a received message for 90s before redelivery — should
                # exceed your worst-case job_handler runtime (Strands ingest
                # ~17s × 3 retries + 7s backoff ≈ 60s).
                "VisibilityTimeout": "90",
                # Keep messages 4 days (max is 14).
                "MessageRetentionPeriod": str(4 * 24 * 3600),
                # Long-poll up to 20s server-side for empty queues.
                "ReceiveMessageWaitTimeSeconds": "20",
            },
        )
        url = resp["QueueUrl"]
        print(f"created queue: {url}  (region={region})")
        print(f"\nadd to .env:\n  QUEUE_MODE=sqs\n  SQS_QUEUE_URL={url}")
        return 0
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        print(f"create_queue failed: {code}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
