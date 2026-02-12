from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite:///./chatbot.db"

    # JWT
    SECRET_KEY: str = "change-this-to-a-secure-random-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "llama3"
    EMBEDDING_MODEL: str = "nomic-embed-text"

    # ChromaDB
    CHROMA_PERSIST_DIR: str = "./chroma_db"

    # PDF manuals directory
    MANUALS_DIR: str = "./data/manuals"

    # RAG
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    TOP_K: int = 5

    class Config:
        env_file = ".env"


settings = Settings()
