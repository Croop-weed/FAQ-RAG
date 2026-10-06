from collections.abc import Sequence

from support_assistant.schemas.faq import FAQRead, FAQStatus
from support_assistant.schemas.retrieval import RetrievalDocument


def build_retrieval_documents(faqs: Sequence[FAQRead]) -> list[RetrievalDocument]:
    """Build stable FAQ-level documents from active records only."""
    active = sorted((faq for faq in faqs if faq.status == FAQStatus.ACTIVE), key=lambda faq: faq.id)
    ids = [faq.id for faq in active]
    if len(ids) != len(set(ids)):
        raise ValueError("FAQ corpus contains duplicate IDs.")
    return [
        RetrievalDocument(
            faq_id=faq.id,
            question=faq.question,
            answer=faq.answer,
            metadata={
                key: value
                for key, value in {
                    "category": faq.category,
                    "source": faq.source,
                    "product": faq.product,
                    "version": faq.version,
                    "region": faq.region,
                    "tags": faq.tags,
                }.items()
                if value is not None
            },
        )
        for faq in active
    ]
