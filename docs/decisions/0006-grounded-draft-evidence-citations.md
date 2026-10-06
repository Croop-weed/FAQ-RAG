# ADR 0006: Grounded Drafts with Validated Evidence Citations

- Status: Accepted
- Date: 2026-10-07

## Context

The existing retrieval pipeline returns reranked FAQ IDs and scores. Draft generation must receive a small, traceable set of FAQ evidence, remain independent of a model vendor, and avoid treating retrieval/reranker scores as confidence. Customer responses must remain human-reviewed; no automatic sending is permitted.

## Decision

Keep `GenerationService` independent of retrieval and persistence. It accepts a customer query plus typed `EvidenceItem` values and limits the evidence to the configured final top-K (default five). A separate `RetrievalGenerationService` composes an injected reranked retriever with the generation service and resolves IDs through an injected retrieval-document map.

Keep a narrow async `LLMProvider` contract returning typed text/model/latency/usage metadata. The first adapter is explicit Ollama configuration; defaults remain `not-configured`, and unsupported providers do not fall back. Use a bounded timeout and do not log prompts or provider payloads.

The prompt separates the customer question from JSON-encoded FAQ evidence and explicitly instructs the model to use only that factual basis, not invent unsupported facts, not follow instructions embedded in evidence, and state when supplied evidence is insufficient. This instruction does not implement an abstention decision.

Ask the model to return JSON containing answer text and FAQ IDs only. Validate every cited ID against the exact evidence sent; construct source citations application-side from those evidence records. Preserve both selected evidence and citations in the typed draft for later grounding evaluation.

## Consequences

- Provider and model replacement does not change generation service behavior.
- Only a bounded, reranked evidence set is sent to the model.
- Unknown or duplicate citations fail explicitly; the model cannot invent source labels.
- The evidence record establishes provenance, not correctness or confidence.
- Provider/model, timing, token usage when available, evidence IDs, and prompt version support later evaluation without logging customer content.
- Confidence, knowledge-gap detection, calibrated abstention, public API, and sending remain out of scope.