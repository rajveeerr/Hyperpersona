"""Compare regex vs comprehend PII redaction on the same text.

Exercises both redactors directly (not through the privacy tool) so the
diff is purely "what does each backend catch?". Run inside worker.

Usage:
    docker compose exec worker python /app/scripts/test_pii.py
"""

import os
import sys

sys.path.insert(0, "/app")

from shared.pii import RegexRedactor, make_pii_redactor  # noqa: E402


SAMPLE = (
    "Hi, my name is John Doe. You can reach me at john.doe@example.com "
    "or 555-123-4567. My SSN is 123-45-6789 and credit card "
    "4111 1111 1111 1111. I'm logging in from 192.168.1.42 "
    "(MAC aa:bb:cc:dd:ee:ff). I live at 1600 Pennsylvania Avenue NW, "
    "Washington DC 20500. My driver's license is D1234567."
)


def _print_result(label: str, redacted: str, entities: list[dict]) -> None:
    print(f"--- {label} ({len(entities)} entities) ---")
    print(f"redacted: {redacted}")
    print("entities:")
    for ent in entities:
        match_text = ent.get("match", "")
        if isinstance(match_text, str) and len(match_text) > 40:
            match_text = match_text[:40] + "..."
        score = ent.get("score")
        score_str = f"  score={score:.3f}" if isinstance(score, float) else ""
        print(f"  - {ent.get('type', '?'):28} {match_text}{score_str}")
    print()


def main() -> int:
    print(f"INPUT:\n{SAMPLE}\n")

    # Regex always available
    regex = RegexRedactor()
    r_text, r_ents = regex.redact(SAMPLE)
    _print_result("REGEX", r_text, r_ents)

    # Comprehend only if PII_MODE asks for it (or AWS creds present)
    mode = os.getenv("PII_MODE", "regex")
    if mode != "comprehend":
        print(f"PII_MODE={mode!r} — skipping comprehend probe.")
        print("(set PII_MODE=comprehend in .env and restart worker to enable)")
        return 0

    comprehend = make_pii_redactor("comprehend", region=os.getenv("AWS_REGION", "us-east-1"))
    c_text, c_ents = comprehend.redact(SAMPLE)
    _print_result("COMPREHEND (layered with regex)", c_text, c_ents)

    # Diff summary
    regex_types = {e.get("type", "") for e in r_ents}
    comp_only = [e for e in c_ents if e.get("type", "").startswith("COMPREHEND_")]
    comp_types = {e.get("type", "") for e in comp_only}
    print(f"regex caught:                {sorted(regex_types)}")
    print(f"comprehend ADDED on top:     {sorted(comp_types)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
