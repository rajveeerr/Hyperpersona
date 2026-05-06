"""PII redaction with two implementations behind a Protocol.

  - RegexRedactor      no AWS calls. Catches email, phone, naive name pairs.
                       Fast (<1ms), free, but limited.
  - ComprehendRedactor calls AWS Comprehend's detect_pii_entities. Catches
                       SSN, credit-card, address, IP, MAC, age, license,
                       date-of-birth, and more. ~200-500ms per call.

Use make_pii_redactor(mode, region) to build the right one. The legacy
module-level `redact()` function is kept for any callers that haven't been
migrated to the factory.
"""

from __future__ import annotations

import logging
import re
from typing import Protocol

from .retry import aws_retry

log = logging.getLogger(__name__)


EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.\w+\b")
PHONE_RE = re.compile(
    r"\b(?:\+?\d{1,3}[\s-]?)?(?:\(\d{3}\)|\d{3})[\s.-]?\d{3}[\s.-]?\d{4}\b"
)
# Crude name heuristic: two consecutive capitalized words, each ≥3 letters.
NAME_RE = re.compile(r"\b[A-Z][a-z]{2,}\s+[A-Z][a-z]{2,}\b")


# --- Protocol -----------------------------------------------------------


class PiiRedactor(Protocol):
    def redact(self, text: str) -> tuple[str, list[dict]]: ...


# --- Regex impl (default, no AWS) ---------------------------------------


def redact(text: str) -> tuple[str, list[dict]]:
    """Module-level regex redactor.

    Kept for backward compat with code that imports `redact` directly.
    Returns (redacted_text, [{type, match}, ...]).
    """
    entities: list[dict] = []

    def _capture(match: re.Match, kind: str) -> str:
        entities.append({"type": kind, "match": match.group(0)})
        return "[REDACTED]"

    text = EMAIL_RE.sub(lambda m: _capture(m, "EMAIL"), text)
    text = PHONE_RE.sub(lambda m: _capture(m, "PHONE"), text)
    text = NAME_RE.sub(lambda m: _capture(m, "NAME"), text)

    return text, entities


class RegexRedactor:
    """Class wrapper around the module-level `redact()` for use behind the
    PiiRedactor protocol."""

    def redact(self, text: str) -> tuple[str, list[dict]]:
        return redact(text)


# --- Comprehend impl (AWS) ----------------------------------------------


class ComprehendRedactor:
    """AWS Comprehend-based PII detector + redactor.

    detect_pii_entities returns offsets; we replace right-to-left so
    earlier offsets stay valid as we splice. Layered with regex as
    defense in depth: Comprehend may miss email/phone formats common in
    e-commerce contexts that regex catches reliably.
    """

    LANGUAGE = "en"

    def __init__(self, region: str) -> None:
        import boto3  # imported lazily so regex-mode users don't need boto3
        self.client = boto3.client("comprehend", region_name=region)

    @aws_retry()
    def _detect(self, text: str) -> dict:
        return self.client.detect_pii_entities(Text=text, LanguageCode=self.LANGUAGE)

    def redact(self, text: str) -> tuple[str, list[dict]]:
        if not text:
            return text, []

        # Layer 1 — regex catches the formats Comprehend sometimes misses.
        text, regex_entities = redact(text)

        # Layer 2 — Comprehend on the already-regex-redacted text. The
        # [REDACTED] tokens won't match anything in Comprehend's PII
        # taxonomy, so this is safe.
        # Errors propagate — privacy is critical, no silent degradation
        # to regex-only. _detect is wrapped with aws_retry, so transient
        # throttling is absorbed; permanent errors (e.g. AccessDenied)
        # raise out to the job_handler retry loop.
        resp = self._detect(text)

        comp_entities = resp.get("Entities", [])
        if not comp_entities:
            return text, regex_entities

        # Replace right-to-left to keep BeginOffset / EndOffset valid.
        result_entities: list[dict] = list(regex_entities)
        for ent in sorted(comp_entities, key=lambda e: -e["BeginOffset"]):
            begin, end = ent["BeginOffset"], ent["EndOffset"]
            match_text = text[begin:end]
            text = text[:begin] + "[REDACTED]" + text[end:]
            result_entities.append({
                "type": f"COMPREHEND_{ent.get('Type', 'UNKNOWN')}",
                "match": match_text,
                "score": ent.get("Score"),
            })

        return text, result_entities


# --- Factory ------------------------------------------------------------


def make_pii_redactor(mode: str, region: str = "us-east-1") -> PiiRedactor:
    """Build a redactor for the current PII_MODE.

    `regex` is the safe default — no AWS dependency. `comprehend` adds
    SSN/CC/IP/MAC/etc detection at ~200-500ms per call.
    """
    if mode == "regex":
        log.info("PiiRedactor: regex")
        return RegexRedactor()
    if mode == "comprehend":
        log.info("PiiRedactor: comprehend (region=%s)", region)
        return ComprehendRedactor(region=region)
    raise ValueError(f"Unknown PII_MODE: {mode!r} (expected 'regex' or 'comprehend')")
