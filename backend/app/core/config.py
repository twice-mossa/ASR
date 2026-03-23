from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    minimax_api_key: str = ""
    minimax_base_url: str = "https://api.minimaxi.com/v1"
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_transcription_model: str = "whisper-large-v3"
    groq_max_upload_mb: int = 24
    whisper_model_size: str = "small"
    database_url: str = "sqlite:///./meeting_assistant.db"
    upload_dir: str = str(BACKEND_ROOT / "data" / "uploads")
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "Audio Memo"
    smtp_use_tls: bool = True
    summary_email_auto_send: bool = False
    ai_runtime_enabled: bool = True
    summary_engine: str = "legacy"
    qa_engine: str = "langgraph"
    vector_store_dir: str = str(BACKEND_ROOT / "data" / "vectorstore")
    chat_provider: str = "minimax"
    chat_model_summary: str = "MiniMax-M2.5"
    chat_model_qa: str = "MiniMax-M2.5"
    chat_model_qa_planner: str = "MiniMax-M2.5"
    chat_model_qa_answer: str = "MiniMax-M2.5"
    embedding_provider: str = "sentence_transformers"
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_device: str = "cpu"
    qa_require_real_embeddings: bool = True
    qa_retrieval_top_k: int = 10
    qa_keyword_top_k: int = 8
    qa_rerank_top_n: int = 4
    qa_neighbor_window: int = 1
    qa_knowledge_pack_wait_seconds: int = 8
    openai_api_key: str = ""
    openai_base_url: str = ""
    jwt_secret_key: str = "replace-me-in-production"
    jwt_expire_minutes: int = 60 * 24 * 7

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
