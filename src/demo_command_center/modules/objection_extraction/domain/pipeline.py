from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256


class EvidenceKind(StrEnum):
    WHATSAPP_MESSAGE = "whatsapp_message"
    POST_DEMO_FEEDBACK = "post_demo_feedback"
    STRUCTURED_OUTCOME = "structured_outcome"
    CONSENTED_TRANSCRIPT = "consented_transcript"
    APPROVED_NOTE = "approved_note"


class ObjectionExpression(StrEnum):
    EXPLICIT = "explicit"
    IMPLICIT = "implicit"


@dataclass(frozen=True, slots=True)
class ObjectionEvidence:
    evidence_ref: str
    kind: EvidenceKind
    redacted_text: str
    permitted: bool
    transcription_consent: bool = False


@dataclass(frozen=True, slots=True)
class FallbackRule:
    rule_id: str
    category: str
    phrases: tuple[str, ...]
    expression: ObjectionExpression
    normalized_objection: str
    root_cause: str
    alternative_interpretation: str
    recommended_next_question: str
    confidence: Decimal


@dataclass(frozen=True, slots=True)
class ObjectionPolicy:
    version: str
    taxonomy: frozenset[str]
    rules: tuple[FallbackRule, ...]
    implicit_confidence_threshold: Decimal
    human_review_threshold: Decimal
    maximum_evidence_items: int
    fallback_prompt_version: str
    fallback_model_version: str

    def __post_init__(self) -> None:
        if not self.version.strip() or not self.taxonomy:
            raise ValueError("objection policy version and taxonomy are required")
        if self.maximum_evidence_items <= 0:
            raise ValueError("maximum evidence items must be positive")
        thresholds = (self.implicit_confidence_threshold, self.human_review_threshold)
        if any(not Decimal(0) <= value <= Decimal(1) for value in thresholds):
            raise ValueError("objection thresholds must be between zero and one")
        for rule in self.rules:
            if rule.category not in self.taxonomy:
                raise ValueError("fallback rule category is outside taxonomy")
            if not Decimal(0) <= rule.confidence <= Decimal(1):
                raise ValueError("fallback rule confidence must be between zero and one")
            if not rule.phrases:
                raise ValueError("fallback rules require evidence phrases")


@dataclass(frozen=True, slots=True)
class Objection:
    objection_id: str
    category: str
    expression: ObjectionExpression
    normalized_objection: str
    root_cause: str
    evidence_refs: tuple[str, ...]
    confidence: Decimal
    alternative_interpretation: str
    recommended_next_question: str
    requires_human_review: bool
    prompt_version: str
    model_version: str


def permitted_evidence(
    evidence: tuple[ObjectionEvidence, ...], policy: ObjectionPolicy
) -> tuple[ObjectionEvidence, ...]:
    approved = tuple(
        item
        for item in evidence
        if item.permitted
        and (item.kind is not EvidenceKind.CONSENTED_TRANSCRIPT or item.transcription_consent)
    )
    return approved[: policy.maximum_evidence_items]


def deterministic_extract(
    evidence: tuple[ObjectionEvidence, ...], policy: ObjectionPolicy
) -> tuple[Objection, ...]:
    approved = permitted_evidence(evidence, policy)
    results: list[Objection] = []
    for rule in policy.rules:
        refs = tuple(
            item.evidence_ref
            for item in approved
            if any(phrase.casefold() in item.redacted_text.casefold() for phrase in rule.phrases)
        )
        if not refs:
            continue
        implicit_below_threshold = (
            rule.expression is ObjectionExpression.IMPLICIT
            and rule.confidence < policy.implicit_confidence_threshold
        )
        requires_review = (
            implicit_below_threshold or rule.confidence < policy.human_review_threshold
        )
        material = f"{policy.version}|{rule.rule_id}|{'|'.join(refs)}"
        results.append(
            Objection(
                sha256(material.encode()).hexdigest(),
                rule.category,
                rule.expression,
                rule.normalized_objection,
                rule.root_cause,
                refs,
                rule.confidence,
                rule.alternative_interpretation,
                rule.recommended_next_question,
                requires_review,
                policy.fallback_prompt_version,
                policy.fallback_model_version,
            )
        )
    return tuple(results)


def validate_extracted_objection(
    objection: Objection,
    stored_evidence_refs: frozenset[str],
    policy: ObjectionPolicy,
) -> Objection:
    if objection.category not in policy.taxonomy:
        raise ValueError("objection category is outside approved taxonomy")
    if not objection.evidence_refs or not set(objection.evidence_refs).issubset(
        stored_evidence_refs
    ):
        raise ValueError("objection evidence is absent or ungrounded")
    if not Decimal(0) <= objection.confidence <= Decimal(1):
        raise ValueError("objection confidence is invalid")
    review = objection.requires_human_review or objection.confidence < policy.human_review_threshold
    if (
        objection.expression is ObjectionExpression.IMPLICIT
        and objection.confidence < policy.implicit_confidence_threshold
    ):
        review = True
    return Objection(
        objection.objection_id,
        objection.category,
        objection.expression,
        objection.normalized_objection,
        objection.root_cause,
        objection.evidence_refs,
        objection.confidence,
        objection.alternative_interpretation,
        objection.recommended_next_question,
        review,
        objection.prompt_version,
        objection.model_version,
    )
