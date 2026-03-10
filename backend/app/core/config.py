from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    minimax_api_key: str = ""
    minimax_base_url: str = "https://api.minimax.chat"
    whisper_model_size: str = "small"
    database_url: str = "sqlite:///./meeting_assistant.db"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
