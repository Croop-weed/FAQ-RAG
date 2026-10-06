class RetrievalError(Exception):
    """Base error for retrieval and evaluation failures."""


class InvalidRetrievalRequest(RetrievalError, ValueError):
    """Raised when a query or retrieval configuration is invalid."""


class EmbeddingError(RetrievalError):
    """Raised when an embedding provider fails or returns invalid vectors."""


class EvaluationDatasetError(RetrievalError, ValueError):
    """Raised when an evaluation dataset cannot be validated."""
