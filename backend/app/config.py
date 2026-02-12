from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite:///./chatbot.db"

    # JWT
    SECRET_KEY: str = "change-this-to-a-secure-random-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Ollama (LLM only)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "llama3"

    # HuggingFace Embedding
    HF_EMBEDDING_MODEL: str = "intfloat/multilingual-e5-large"
    HF_CACHE_DIR: str = "./models"

    # ChromaDB
    CHROMA_PERSIST_DIR: str = "./chroma_db"

    # PDF manuals directory
    MANUALS_DIR: str = "./data/manuals"

    # RAG
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 100
    TOP_K: int = 5
    DISTANCE_THRESHOLD: float = 0.4

    # Service identity — one chatbot per container
    SERVICE_NAME: str = "경영혁신팀 챗봇"
    SERVICE_DESCRIPTION: str = "병원 경영혁신팀 매뉴얼 기반 질의응답 서비스"
    COLLECTION_NAME: str = "innovation_team"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
