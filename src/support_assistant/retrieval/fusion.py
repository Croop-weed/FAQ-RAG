from collections import defaultdict
from collections.abc import Sequence
from typing import Protocol

from support_assistant.retrieval.exceptions import InvalidRetrievalRequest
from support_assistant.schemas.retrieval import RetrievalCandidate


class RankFusionStrategy(Protocol):
    def fuse(
        self,
        ranked_lists: Sequence[Sequence[RetrievalCandidate]],
        *,
        top_k: int,
    ) -> list[RetrievalCandidate]: ...


class ReciprocalRankFusion:
    """Fuse candidate rankings by rank positions, never by source score values."""

    name = "rrf"

    def __init__(self, rank_constant: int = 60) -> None:
        if rank_constant < 1:
            raise InvalidRetrievalRequest("RRF rank constant must be positive.")
        self.rank_constant = rank_constant

    def fuse(
        self,
        ranked_lists: Sequence[Sequence[RetrievalCandidate]],
        *,
        top_k: int,
    ) -> list[RetrievalCandidate]:
        if top_k < 1:
            raise InvalidRetrievalRequest("Fusion top_k must be at least 1.")
        scores: dict[str, float] = defaultdict(float)
        source_ranks: dict[str, dict[str, int]] = defaultdict(dict)
        for list_index, candidates in enumerate(ranked_lists):
            seen: set[str] = set()
            for candidate in candidates:
                faq_id = candidate.faq_id
                if faq_id in seen:
                    raise InvalidRetrievalRequest(
                        f"Ranking {list_index} contains duplicate FAQ ID '{faq_id}'."
                    )
                seen.add(faq_id)
                rank = candidate.rank
                scores[faq_id] += 1.0 / (self.rank_constant + rank)
                source_name = (
                    candidate.retrieval_stage
                    if candidate.retrieval_stage != "retrieval"
                    else str(list_index)
                )
                source_ranks[faq_id][source_name] = rank

        ordered_ids = sorted(scores, key=lambda faq_id: (-scores[faq_id], faq_id))[:top_k]
        return [
            RetrievalCandidate(
                document_id=faq_id,
                score=scores[faq_id],
                rank=rank,
                retrieval_stage=self.name,
                metadata={"source_ranks": source_ranks[faq_id]},
            )
            for rank, faq_id in enumerate(ordered_ids, start=1)
        ]
