"""Idempotently create the S3 bucket used for trace sync.

Reads S3_TRACES_BUCKET + AWS_REGION from env. Creates the bucket if it
doesn't exist. Safe to re-run.

Usage:
    docker compose exec worker python /app/scripts/setup_s3.py
or:
    make setup-s3
"""

import os
import sys

import boto3
from botocore.exceptions import ClientError


def main() -> int:
    bucket = os.getenv("S3_TRACES_BUCKET", "").strip()
    region = os.getenv("AWS_REGION", "us-east-1")
    if not bucket:
        print("FAIL: S3_TRACES_BUCKET is not set", file=sys.stderr)
        return 1

    s3 = boto3.client("s3", region_name=region)

    try:
        s3.head_bucket(Bucket=bucket)
        print(f"bucket already exists: s3://{bucket}")
        return 0
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code not in ("404", "NoSuchBucket", "NotFound"):
            # 403 = exists but not ours, or the role can't access — common in
            # Workshop Studio. Tell the user clearly.
            print(f"head_bucket failed for s3://{bucket}: {code} — "
                  f"either the name is taken globally, or this role can't access it",
                  file=sys.stderr)
            return 1

    try:
        kwargs = {"Bucket": bucket}
        # us-east-1 is the only region that rejects an explicit
        # LocationConstraint=us-east-1 (legacy AWS quirk).
        if region != "us-east-1":
            kwargs["CreateBucketConfiguration"] = {"LocationConstraint": region}
        s3.create_bucket(**kwargs)
        print(f"created bucket: s3://{bucket} (region={region})")
        return 0
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("BucketAlreadyOwnedByYou",):
            print(f"bucket already exists (owned by us): s3://{bucket}")
            return 0
        print(f"create_bucket failed: {code}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
