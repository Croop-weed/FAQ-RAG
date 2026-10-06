import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

import numpy as np
import structlog
from numpy.typing import NDArray

from support_assistant.retrieval.exceptions import EmbeddingError

logger = structlog.get_logger(__name__)


class EmbeddingProvider(Protocol):
    @property
    def model_name(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    def embed_documents(self, texts: Sequence[str]) -> Sequence[Sequence[float]]: ...

    def embed_query(self, text: str) -> Sequence[float]: ...


class SentenceTransformerEmbeddingProvider:
    """Explicit Sentence Transformers adapter; construction loads the configured model."""

    def __init__(self, model_name: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(model_name)
            self._model_name = model_name
            dimension = self._model.get_embedding_dimension()
            if dimension is None or dimension < 1:
                raise EmbeddingError("Embedding model reported an invalid dimension.")
            self._dimension = dimension
        except EmbeddingError:
            raise
        except Exception as error:
            raise EmbeddingError(
                f"Could not load embedding model '{model_name}'. Check model access and cache."
            ) from error
        logger.info(
            "embedding_model_loaded",
            model_name=self._model_name,
            embedding_dimension=self._dimension,
        )

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_documents(self, texts: Sequence[str]) -> NDArray[np.float32]:
        return self._encode(texts)

    def embed_query(self, text: str) -> NDArray[np.float32]:
        return self._encode([text])[0]

    def _encode(self, texts: Sequence[str]) -> NDArray[np.float32]:
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)
        try:
            vectors = np.asarray(
                self._model.encode(
                    list(texts),
                    convert_to_numpy=True,
                    normalize_embeddings=False,
                    show_progress_bar=False,
                ),
                dtype=np.float32,
            )
        except Exception as error:
            raise EmbeddingError("Embedding generation failed.") from error
        if vectors.ndim != 2 or vectors.shape != (len(texts), self.dimension):
            raise EmbeddingError("Embedding provider returned an inconsistent vector shape.")
        if not np.isfinite(vectors).all():
            raise EmbeddingError("Embedding provider returned non-finite values.")
        return vectors


class DocumentEmbeddingCache:
    """Local content-addressed .npz cache for corpus embeddings."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def get_or_create(
        self,
        provider: EmbeddingProvider,
        documents: Sequence[tuple[str, str]],
    ) -> NDArray[np.float32]:
        key_payload = json.dumps(
            {"model": provider.model_name, "documents": list(documents)},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        cache_key = hashlib.sha256(key_payload.encode("utf-8")).hexdigest()
        cache_path = self.directory / f"{cache_key}.npz"
        if cache_path.is_file():
            try:
                with np.load(cache_path, allow_pickle=False) as archive:
                    vectors = np.asarray(archive["embeddings"], dtype=np.float32)
                vectors = self._validate(vectors, len(documents), provider.dimension)
                logger.info("document_embeddings_cache_hit", count=len(documents))
                return vectors
            except (OSError, KeyError, ValueError, EmbeddingError):
                cache_path.unlink(missing_ok=True)

        if documents:
            vectors = np.asarray(
                provider.embed_documents([content for _, content in documents]),
                dtype=np.float32,
            )
        else:
            vectors = np.empty((0, provider.dimension), dtype=np.float32)
        vectors = self._validate(vectors, len(documents), provider.dimension)
        logger.info(
            "embeddings_generated",
            count=len(documents),
            embedding_dimension=provider.dimension,
        )
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary_path = cache_path.with_suffix(".tmp.npz")
        np.savez_compressed(temporary_path, embeddings=vectors)
        temporary_path.replace(cache_path)
        return vectors

    @staticmethod
    def _validate(vectors: NDArray[np.float32], count: int, dimension: int) -> NDArray[np.float32]:
        if vectors.shape != (count, dimension) or not np.isfinite(vectors).all():
            raise EmbeddingError("Cached document embeddings have an invalid shape or values.")
        return vectors
