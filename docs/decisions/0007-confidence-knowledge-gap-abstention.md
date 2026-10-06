# ADR 0007: Confidence Assessment, Knowledge-Gap Detection, and Abstention Policy

- Status: Accepted
- Date: 2026-10-07

## Context

Phase 6 introduced grounded draft generation with citation provenance, but left confidence scoring, knowledge-gap evaluation, and abstention behavior for Phase 7. Models may produce plausible-sounding answers even when retrieved evidence is weak, out-of-domain, or insufficient. Customer support applications require a reliable, explainable decision layer that abstains from answering when knowledge is inadequate rather than presenting unsupported claims as trustworthy.

Crucially, self-reported confidence from LLMs (e.g., asking "How confident are you on a scale of 0 to 1?") is uncalibrated and unreliable. Confidence must be derived from measurable application-level signals.

## Decision

1. **Domain Model & Three-State Policy:**
   Define `ConfidenceDecision` enum with three explicit states: `ACCEPT`, `REVIEW`, and `ABSTAIN`.
   - `ACCEPT`: Strong evidence supports the draft; safe to present as a human-review draft.
   - `REVIEW`: Evidence is relevant but support is uncertain or score margin is narrow.
   - `ABSTAIN`: Evidence is insufficient, a knowledge gap is detected, or the answer contains unsupported claims.
   Even `ACCEPT` indicates safety for internal agent draft presentation, not automatic customer sending.

2. **Measurable Confidence Signals:**
   Calculate confidence from measurable signals: top cross-encoder reranker score, score margin between top candidate FAQs, citation validity, evidence support score, and knowledge-gap checks. Do NOT use raw RRF or BM25/vector scores directly as probabilities. Sigmoid normalization scales reranker scores into [0, 1]. The heuristic scoring formula is provisional and explicitly documented as requiring calibration against human-labeled golden evaluation datasets.

3. **Replaceable Evidence Support Evaluator:**
   Isolate answer-evidence support evaluation behind `EvidenceSupportEvaluator` protocol. Implement `HeuristicEvidenceSupportEvaluator` checking sentence-level token overlap, citation provenance, and detecting unsupported claims in generated text. This contract can later be swapped for an NLI model, LLM judge, or specialized verifier without altering application services.

4. **Dedicated Knowledge-Gap Service:**
   Implement `KnowledgeGapService` to inspect the query, retrieved evidence, and optional draft text. It detects knowledge gaps (empty evidence, low reranker score below threshold, unmatched query terms, or draft refusal phrases) without executing retrieval, calling the LLM directly, or mutating persistence.

5. **Structured Abstention Behavior:**
   When `decision` is `ABSTAIN`, `Phase7DraftService` returns a structured abstention result with `answer: None`, a human-readable explainable reason, confidence score, citations for any retrieved evidence, and underlying assessment metadata.

6. **Configurable Thresholds:**
   Centralize confidence thresholds (`confidence_accept_threshold`, `confidence_review_threshold`, `min_evidence_reranker_score`, `min_supporting_evidence_count`, `knowledge_gap_threshold`) in `core.config.Settings`.

## Consequences

- The application explicitly distinguishes between strongly supported answers, uncertain drafts, and knowledge gaps.
- The system explicitly abstains (`answer: None`) when evidence is insufficient, preventing hallucinated answers from reaching agents.
- Confidence decisions produce explainable human-readable reasons for logs, agent UI, and debugging without exposing internal math to customers.
- Replaceable contracts allow future upgrade to NLI or LLM judges for grounding evaluation without refactoring confidence or pipeline services.
- Heuristic scoring is provisional until calibrated against larger golden evaluation benchmarks.
