from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    minimax_api_key: str = ""
    minimax_base_url: str = "https://api.minimax.chat"
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_transcription_model: str = "whisper-large-v3"
    groq_max_upload_mb: int = 24
    whisper_model_size: str = "small"
    database_url: str = "sqlite:///./meeting_assistant.db"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
