from __future__ import annotations

import hashlib
import math
from functools import lru_cache

from langchain_core.embeddings import Embeddings
from sentence_transformers import SentenceTransformer


class LocalHashEmbeddings(Embeddings):
    """Deterministic multilingual-friendly hashing embeddings.

    This is intentionally lightweight so the project can adopt LangChain
    without forcing a heavyweight embedding model download in local/dev.
    """

    def __init__(self, *, dimensions: int = 256, ngram_range: tuple[int, int] = (2, 4)) -> None:
        self.dimensions = max(64, dimensions)
        self.ngram_range = ngram_range

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        normalized = self._normalize(text)
        vector = [0.0] * self.dimensions
        if not normalized:
            return vector

        grams = self._char_ngrams(normalized)
        for gram in grams:
            digest = hashlib.md5(gram.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm <= 0:
            return vector
        return [value / norm for value in vector]

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join((text or "").strip().lower().split())

    def _char_ngrams(self, text: str) -> list[str]:
        compact = text.replace(" ", "")
        if not compact:
            return []

        grams: list[str] = []
        start_n, end_n = self.ngram_range
        for size in range(start_n, end_n + 1):
            if len(compact) < size:
                continue
            for index in range(len(compact) - size + 1):
                grams.append(compact[index : index + size])

        if not grams:
            grams.append(compact)
        return grams


@lru_cache(maxsize=4)
def _load_sentence_transformer(model_name: str, device: str) -> SentenceTransformer:
    kwargs: dict[str, str] = {}
    if device:
        kwargs["device"] = device
    return SentenceTransformer(model_name, **kwargs)


class SentenceTransformerEmbeddings(Embeddings):
    def __init__(self, *, model_name: str, device: str = "cpu") -> None:
        self.model_name = model_name
        self.device = device or "cpu"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        normalized = [self._normalize_document(text) for text in texts if (text or "").strip()]
        if not normalized:
            return []
        model = _load_sentence_transformer(self.model_name, self.device)
        vectors = model.encode(normalized, normalize_embeddings=True)
        return [vector.tolist() for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        model = _load_sentence_transformer(self.model_name, self.device)
        vector = model.encode(self._normalize_query(text), normalize_embeddings=True)
        return vector.tolist()

    def _normalize_query(self, text: str) -> str:
        normalized = " ".join((text or "").strip().split())
        if "bge" in self.model_name.lower():
            return f"为这个句子生成表示以用于检索相关文章：{normalized}"
        return normalized

    @staticmethod
    def _normalize_document(text: str) -> str:
        return " ".join((text or "").strip().split())
