"""Verify real Bedrock is live in this container.

Reports BEDROCK_MODE, AWS cred shape, factory type, and runs a real
embed+generate. Prints PASS or FAIL with a reason.

Designed to run in both worker and server containers (no top-level
imports that exist only in one). Wired up via `make verify-bedrock`,
which runs this script in both containers.
"""

import os
import sys

from shared.bedrock import (
    BedrockClient,
    MockBedrockClient,
    make_bedrock_client,
)


def main() -> int:
    mode = os.getenv("BEDROCK_MODE", "mock")
    region = os.getenv("BEDROCK_REGION", "us-east-1")
    text_model = os.getenv("BEDROCK_TEXT_MODEL", "")
    embed_model = os.getenv("BEDROCK_EMBED_MODEL", "")
    akid = os.getenv("AWS_ACCESS_KEY_ID", "")
    has_session = bool(os.getenv("AWS_SESSION_TOKEN"))

    print(f"BEDROCK_MODE     : {mode}")
    print(f"BEDROCK_REGION   : {region}")
    print(f"TEXT_MODEL       : {text_model}")
    print(f"EMBED_MODEL      : {embed_model}")
    print(f"AKID prefix      : {akid[:4] or '(empty)'}")
    print(f"SESSION_TOKEN    : {'present' if has_session else 'MISSING'}")

    client = make_bedrock_client(
        mode=mode, region=region,
        text_model=text_model, embed_model=embed_model,
    )
    impl = type(client).__name__
    print(f"factory returned : {impl}")

    expected = BedrockClient if mode == "real" else MockBedrockClient
    if not isinstance(client, expected):
        print(f"FAIL — expected {expected.__name__} for mode={mode}, got {impl}")
        return 1

    try:
        vec = client.embed("hello")
        gen = client.generate("Reply with the single word: ALIVE")
    except Exception as e:
        print(f"FAIL — Bedrock call raised {type(e).__name__}: {e}")
        return 1

    print(f"embed dim        : {len(vec)}  sample: {[round(x, 4) for x in vec[:3]]}")
    print(f"generate         : {gen[:80]}")

    if mode == "real" and gen.startswith("[mock]"):
        print("FAIL — real mode but generate looks like a mock response")
        return 1
    if mode == "real" and not has_session and akid.startswith("ASIA"):
        print("FAIL — temp creds (ASIA) without AWS_SESSION_TOKEN")
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
