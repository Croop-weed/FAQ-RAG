from collections.abc import Sequence

import numpy as np
from huggingface_hub import InferenceClient
from numpy.typing import NDArray

from support_assistant.retrieval.exceptions import EmbeddingError


class HuggingFaceEmbeddingProvider:
    """Embedding adapter backed by Hugging Face Inference Providers."""

    def __init__(
        self,
        model_name: str,
        api_key: str,
    ) -> None:
        if not api_key:
            raise EmbeddingError(
                "SUPPORT_ASSISTANT_HF_API_KEY is not configured."
            )

        self._model_name = model_name

        try:
            self._client = InferenceClient(
                api_key=api_key,
                provider="auto",
            )
        except Exception as error:
            raise EmbeddingError(
                "Could not initialize Hugging Face client."
            ) from error

        # BAAI/bge-small-en-v1.5 produces 384-dimensional vectors.
        self._dimension = 384

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_documents(
        self,
        texts: Sequence[str],
    ) -> NDArray[np.float32]:
        if not texts:
            return np.empty(
                (0, self.dimension),
                dtype=np.float32,
            )

        try:
            result = self._client.feature_extraction(
                list(texts),
                model=self._model_name,
            )
        except Exception as error:
            raise EmbeddingError(
                "Hugging Face document embedding failed."
            ) from error

        vectors = np.asarray(result, dtype=np.float32)

        if vectors.ndim == 3:
            # Mean-pool token embeddings (N, S, D) -> (N, D)
            vectors = np.mean(vectors, axis=1)

        if vectors.ndim != 2:
            raise EmbeddingError(
                "Hugging Face returned invalid document embedding shape."
            )

        if vectors.shape != (len(texts), self.dimension):
            raise EmbeddingError(
                f"Expected embeddings with shape "
                f"({len(texts)}, {self.dimension}), "
                f"received {vectors.shape}."
            )

        if not np.isfinite(vectors).all():
            raise EmbeddingError(
                "Hugging Face returned non-finite embeddings."
            )

        return vectors

    def embed_query(
        self,
        text: str,
    ) -> NDArray[np.float32]:
        if not text.strip():
            raise EmbeddingError(
                "Embedding query cannot be empty."
            )

        try:
            result = self._client.feature_extraction(
                text,
                model=self._model_name,
            )
        except Exception as error:
            raise EmbeddingError(
                "Hugging Face query embedding failed."
            ) from error

        vectors = np.asarray(result, dtype=np.float32)

        if vectors.ndim == 3 and vectors.shape[0] == 1:
            vector = np.mean(vectors[0], axis=0)
        elif vectors.ndim == 2:
            if vectors.shape[0] == 1:
                vector = vectors[0]
            else:
                vector = np.mean(vectors, axis=0)
        elif vectors.ndim == 1:
            vector = vectors
        else:
            raise EmbeddingError(
                "Hugging Face returned invalid query embedding shape."
            )

        if vector.shape != (self.dimension,):
            raise EmbeddingError(
                f"Expected query embedding dimension "
                f"{self.dimension}, got {vector.shape}."
            )

        if not np.isfinite(vector).all():
            raise EmbeddingError(
                "Hugging Face returned non-finite query embedding."
            )

        return vector