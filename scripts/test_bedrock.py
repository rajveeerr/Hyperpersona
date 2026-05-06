"""Sanity test for the Bedrock wrapper.

Runs in whichever mode BEDROCK_MODE is set to (default: mock).
Usage (inside worker container):
  python /app/scripts/test_bedrock.py
or:
  make test-bedrock
"""

import os

from shared.bedrock import make_bedrock_client


def main() -> None:
    mode = os.getenv("BEDROCK_MODE", "real")
    region = os.getenv("BEDROCK_REGION", "us-east-1")
    text_model = os.getenv("BEDROCK_TEXT_MODEL", "anthropic.claude-sonnet-4-5-20250929-v1:0")
    embed_model = os.getenv("BEDROCK_EMBED_MODEL", "amazon.titan-embed-text-v2:0")

    print(f"mode:        {mode}")
    print(f"region:      {region}")
    print(f"text_model:  {text_model}")
    print(f"embed_model: {embed_model}")
    print()

    client = make_bedrock_client(
        mode=mode,
        region=region,
        text_model=text_model,
        embed_model=embed_model,
    )

    vec = client.embed("hello world")
    print(f"embed dims:   {len(vec)}")
    print(f"embed sample: {[round(x, 4) for x in vec[:5]]}")
    print()

    text = client.generate("What is 2+2?")
    print(f"generate:     {text}")


if __name__ == "__main__":
    main()
