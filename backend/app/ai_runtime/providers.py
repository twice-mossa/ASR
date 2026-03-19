from __future__ import annotations

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.ai_runtime.embeddings import LocalHashEmbeddings, SentenceTransformerEmbeddings
from app.core.config import settings


def _chat_provider_settings() -> tuple[str, str]:
    provider = (settings.chat_provider or "minimax").strip().lower()
    if provider == "minimax":
        return settings.minimax_api_key, settings.minimax_base_url
    if provider == "openai":
        return settings.openai_api_key, settings.openai_base_url
    raise ValueError(f"Unsupported chat provider: {settings.chat_provider}")


def chat_model_for_summary() -> ChatOpenAI:
    api_key, base_url = _chat_provider_settings()
    if not api_key:
        raise ValueError("Missing chat model API key for summary runtime")
    return ChatOpenAI(
        api_key=api_key,
        base_url=base_url or None,
        model=settings.chat_model_summary or "MiniMax-M2.5",
        temperature=0.1,
    )


def chat_model_for_qa() -> ChatOpenAI:
    api_key, base_url = _chat_provider_settings()
    if not api_key:
        raise ValueError("Missing chat model API key for QA runtime")
    return ChatOpenAI(
        api_key=api_key,
        base_url=base_url or None,
        model=settings.chat_model_qa or settings.chat_model_summary or "MiniMax-M2.5",
        temperature=0.2,
    )


def embedding_model(*, require_real: bool = False):
    provider = (settings.embedding_provider or "local").strip().lower()
    if provider == "local":
        if require_real:
            raise ValueError(
                "QA runtime requires a real semantic embedding model. "
                "Configure EMBEDDING_PROVIDER=openai or EMBEDDING_PROVIDER=sentence_transformers."
            )
        return LocalHashEmbeddings()
    if provider == "sentence_transformers":
        return SentenceTransformerEmbeddings(
            model_name=settings.embedding_model or "BAAI/bge-small-zh-v1.5",
            device=settings.embedding_device or "cpu",
        )
    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("Missing OpenAI API key for embedding runtime")
        return OpenAIEmbeddings(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
            model=settings.embedding_model or "text-embedding-3-small",
        )
    raise ValueError(f"Unsupported embedding provider: {settings.embedding_provider}")
