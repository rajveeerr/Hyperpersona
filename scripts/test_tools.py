"""End-to-end test for all four agent tools.

Wires up real DynamoDB Local, the (mock or real) BedrockClient, and an
InMemoryVectorStore. Exercises each tool with canned inputs and prints
the results so you can see the wiring works.

Usage: make test-tools
Prereq: make setup-db && make seed-consent
"""

import os

from shared.bedrock import make_bedrock_client
from shared.dynamo import DynamoClient
from shared.vector_store import InMemoryVectorStore

from src.agents.tools import (
    analyzer_tool,
    privacy_tool,
    recommender_tool,
    verifier_tool,
)


def _section(title: str) -> None:
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


def main() -> None:
    dynamo = DynamoClient(
        endpoint=os.getenv("DYNAMODB_ENDPOINT", "http://localhost:8001"),
        region=os.getenv("AWS_REGION", "us-east-1"),
    )
    bedrock = make_bedrock_client(
        mode=os.getenv("BEDROCK_MODE", "real"),
        region=os.getenv("BEDROCK_REGION", "us-east-1"),
        text_model=os.getenv("BEDROCK_TEXT_MODEL", "anthropic.claude-sonnet-4-5-20250929-v1:0"),
        embed_model=os.getenv("BEDROCK_EMBED_MODEL", "amazon.titan-embed-text-v2:0"),
    )
    vectors = InMemoryVectorStore()

    _section("PRIVACY TOOL")

    r = privacy_tool.check_privacy(
        "cust_1",
        "John Doe bought trail shoes at john@example.com",
        dynamo,
    )
    print(f"cust_1 (has consent):  {r}")

    r = privacy_tool.check_privacy("cust_no_consent", "Some text", dynamo)
    print(f"cust_no_consent:       {r}")

    r = privacy_tool.check_privacy("cust_unknown", "Some text", dynamo)
    print(f"cust_unknown:          {r}")

    _section("ANALYZER TOOL")

    r = analyzer_tool.analyze_behavior(
        customer_id="cust_1",
        event_text="Customer viewed trail running shoes and added Salomon X Ultra to cart",
        event_id="evt_test_1",
        bedrock=bedrock,
        vectors=vectors,
    )
    print(f"analyze_behavior:      {r}")

    _section("RECOMMENDER TOOL")

    r = recommender_tool.generate_recommendation(
        customer_id="cust_1",
        context="looking for outdoor running gear",
        bedrock=bedrock,
        vectors=vectors,
    )
    print(f"facts_used:            {r['facts_used']}")
    print(f"behaviors_used:        {r['behaviors_used']}")
    print(f"offer:                 {r['offer'][:200]}")

    _section("VERIFIER TOOL")

    r = verifier_tool.verify_recommendation(
        draft_offer="We recommend Salomon trail shoes",
        source_context="Customer searched for trail running shoes and added Salomon X Ultra to cart",
        bedrock=bedrock,
    )
    print(f"status:                {r['status']}")
    print(f"final_offer:           {r['final_offer'][:200]}")


if __name__ == "__main__":
    main()
