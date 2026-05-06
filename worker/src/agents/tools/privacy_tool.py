"""Privacy gate: consent check + PII redaction.

Two entry points, same logic:
  - check_privacy(...)                   plain function for ManualSupervisor
  - make_privacy_tool(dynamo, redactor)  Strands @tool for StrandsSupervisor

Both delegate to the injected redactor (PII_MODE=regex|comprehend).
"""

import logging

from shared.dynamo import DynamoClient
from shared.pii import PiiRedactor, RegexRedactor

log = logging.getLogger(__name__)

# Default redactor — used when callers don't pass one in. Preserves the
# old "no-arg" call shape for any unmigrated test or script.
_DEFAULT_REDACTOR: PiiRedactor = RegexRedactor()


def check_privacy(
    customer_id: str,
    text: str,
    dynamo: DynamoClient,
    redactor: PiiRedactor | None = None,
    required_scope: str = "personalization",
) -> dict:
    """Check consent and redact PII.

    Returns:
        {"allowed": False, "reason": ...}                                   if blocked
        {"allowed": True, "redacted_text": ..., "pii_found": int, ...}      if allowed
    """
    consent = dynamo.get_consent(customer_id)
    if not consent:
        return {"allowed": False, "reason": "no_consent_record"}

    scopes = consent.get("scopes") or set()
    if required_scope not in scopes:
        return {"allowed": False, "reason": f"scope_missing:{required_scope}"}

    redactor = redactor or _DEFAULT_REDACTOR
    redacted_text, entities = redactor.redact(text)
    log.info("privacy: cust=%s pii=%d redactor=%s",
             customer_id, len(entities), type(redactor).__name__)
    return {
        "allowed": True,
        "redacted_text": redacted_text,
        "pii_found": len(entities),
        "pii_entities": entities,
    }


def make_privacy_tool(dynamo: DynamoClient, redactor: PiiRedactor | None = None):
    """Return a Strands @tool that closes over dynamo + redactor.

    Strands reads the inner function's signature to build the JSON schema
    Claude sees, so dependencies must be closed over rather than passed as
    positional args.
    """
    from strands import tool

    redactor = redactor or _DEFAULT_REDACTOR

    @tool
    def check_privacy_tool(customer_id: str, text: str) -> dict:
        """Check the customer's consent record and redact PII from the text.

        If consent is missing or the 'personalization' scope is not granted,
        returns allowed=False with a reason. Otherwise returns the redacted
        text and the count of PII entities found.

        Args:
            customer_id: the customer making the request
            text: the raw event text to redact

        Returns:
            dict with 'allowed' (bool) and either 'reason' (when blocked) or
            'redacted_text' + 'pii_found' (when allowed).
        """
        return check_privacy(customer_id, text, dynamo, redactor=redactor)

    return check_privacy_tool
