import re
from collections.abc import Sequence
from typing import Protocol

from support_assistant.schemas.confidence import EvidenceSupportResult
from support_assistant.schemas.draft import EvidenceItem

STOP_WORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "but",
    "if",
    "because",
    "as",
    "what",
    "when",
    "where",
    "how",
    "which",
    "who",
    "this",
    "that",
    "these",
    "those",
    "then",
    "just",
    "so",
    "than",
    "such",
    "both",
    "through",
    "about",
    "for",
    "is",
    "of",
    "to",
    "in",
    "it",
    "you",
    "your",
    "we",
    "our",
    "are",
    "be",
    "by",
    "on",
    "with",
    "can",
    "could",
    "will",
    "would",
    "should",
    "has",
    "have",
    "had",
}


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"\b\w+\b", text.lower())
    return {w for w in words if w not in STOP_WORDS and len(w) > 1}


def _split_sentences(text: str) -> list[str]:
    lines = text.splitlines()
    sentences: list[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = re.split(r"(?<=[.!?])\s+", line)
        for p in parts:
            p_clean = p.strip()
            if p_clean:
                sentences.append(p_clean)
    return sentences


class EvidenceSupportEvaluator(Protocol):
    def evaluate(
        self,
        query: str,
        answer: str,
        evidence: Sequence[EvidenceItem],
        cited_faq_ids: Sequence[str] | None = None,
    ) -> EvidenceSupportResult: ...


class HeuristicEvidenceSupportEvaluator:
    """Provisional heuristic evidence support evaluator based on lexical overlap.

    Note: This heuristic evaluator provides a baseline check for evidence grounding.
    It must be calibrated and evaluated against human-labeled golden datasets.
    """

    def __init__(self, *, min_sentence_overlap: float = 0.30) -> None:
        self.min_sentence_overlap = min_sentence_overlap

    def evaluate(
        self,
        query: str,
        answer: str,
        evidence: Sequence[EvidenceItem],
        cited_faq_ids: Sequence[str] | None = None,
    ) -> EvidenceSupportResult:
        if not answer.strip():
            return EvidenceSupportResult(
                supported=False,
                support_score=0.0,
                supporting_evidence_ids=[],
                unsupported_claims=["Empty answer text"],
                citation_validity=0.0,
                evidence_relevance_scores={},
                explanation="Answer is empty.",
            )

        if not evidence:
            return EvidenceSupportResult(
                supported=False,
                support_score=0.0,
                supporting_evidence_ids=[],
                unsupported_claims=_split_sentences(answer),
                citation_validity=0.0,
                evidence_relevance_scores={},
                explanation="No evidence provided to support the answer.",
            )

        evidence_by_id = {item.faq_id: item for item in evidence}
        evidence_tokens = {
            item.faq_id: _tokenize(f"{item.question} {item.answer}") for item in evidence
        }

        # Calculate relevance of evidence to query
        query_tokens = _tokenize(query)
        evidence_relevance: dict[str, float] = {}
        for item in evidence:
            item_tokens = evidence_tokens[item.faq_id]
            if not query_tokens:
                relevance = 1.0
            else:
                query_overlap = len(query_tokens & item_tokens)
                relevance = query_overlap / float(len(query_tokens))
            evidence_relevance[item.faq_id] = round(relevance, 4)

        # Check citations validity
        cited_ids = list(cited_faq_ids or [])
        if cited_ids:
            valid_citations = [cid for cid in cited_ids if cid in evidence_by_id]
            citation_validity = len(valid_citations) / float(len(cited_ids))
        else:
            citation_validity = 1.0

        sentences = _split_sentences(answer)
        if not sentences:
            sentences = [answer.strip()]

        supporting_faq_ids: set[str] = set()
        unsupported_claims: list[str] = []
        supported_sentences_count = 0

        # Primary source pool for grounding: cited evidence if provided, else all supplied evidence
        grounding_faq_ids = [cid for cid in cited_ids if cid in evidence_by_id] or list(
            evidence_by_id.keys()
        )

        for sentence in sentences:
            sent_tokens = _tokenize(sentence)
            if not sent_tokens:
                supported_sentences_count += 1
                continue

            max_overlap = 0.0
            best_faq_id: str | None = None

            for faq_id in grounding_faq_ids:
                faq_toks = evidence_tokens[faq_id]
                if not faq_toks:
                    continue
                intersection = len(sent_tokens & faq_toks)
                overlap = intersection / float(len(sent_tokens))
                if overlap > max_overlap:
                    max_overlap = overlap
                    best_faq_id = faq_id

            if max_overlap >= self.min_sentence_overlap and best_faq_id is not None:
                supported_sentences_count += 1
                supporting_faq_ids.add(best_faq_id)
            else:
                unsupported_claims.append(sentence)

        support_ratio = supported_sentences_count / float(len(sentences))
        final_support_score = round(support_ratio * citation_validity, 4)

        is_supported = (
            final_support_score >= 0.70
            and len(unsupported_claims) == 0
            and citation_validity == 1.0
        )

        explanation_parts = [
            f"{supported_sentences_count}/{len(sentences)} sentence(s) supported by evidence."
        ]
        if unsupported_claims:
            explanation_parts.append(
                f"{len(unsupported_claims)} claim(s) lack sufficient evidence support."
            )
        if citation_validity < 1.0:
            explanation_parts.append(
                f"Citation validity is {citation_validity:.2f} due to invalid citations."
            )

        return EvidenceSupportResult(
            supported=is_supported,
            support_score=final_support_score,
            supporting_evidence_ids=sorted(supporting_faq_ids),
            unsupported_claims=unsupported_claims,
            citation_validity=citation_validity,
            evidence_relevance_scores=evidence_relevance,
            explanation=" ".join(explanation_parts),
        )
