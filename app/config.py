from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    groq_api_key: str = ""
    llm_model: str = "llama-3.3-70b-versatile"
    embedding_model: str = "intfloat/multilingual-e5-small"
    relevance_threshold: float = 0.80
    top_k: int = 5
    gemini_api_key: str = ""
    
    # Correctly grouped inside the class definition
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""


settings = Settings()
