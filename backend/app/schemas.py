from datetime import datetime

from pydantic import BaseModel, EmailStr


# --- Auth ---
class UserCreate(BaseModel):
    username: str
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str


# --- Chatbot ---
class ChatbotCreate(BaseModel):
    name: str
    description: str | None = None
    icon: str = "🤖"
    llm_model: str | None = None  # Ollama model name; None = server default
    system_prompt: str | None = None
    temperature: float = 0.7
    top_k: int = 5
    distance_threshold: float = 0.4
    chunk_size: int = 500
    chunk_overlap: int = 100


class ChatbotResponse(BaseModel):
    id: str
    name: str
    description: str | None
    collection_name: str
    icon: str | None = "🤖"
    creator_id: str | None = None
    llm_model: str | None = None
    system_prompt: str | None = None
    temperature: float | None = 0.7
    top_k: int | None = 5
    distance_threshold: float | None = 0.4
    chunk_size: int | None = 500
    chunk_overlap: int | None = 100
    created_at: datetime

    class Config:
        from_attributes = True


# --- Conversation ---
class ConversationCreate(BaseModel):
    chatbot_id: str
    title: str | None = None


class ConversationResponse(BaseModel):
    id: str
    title: str | None
    chatbot_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Message ---
class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    references: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationWithMessages(ConversationResponse):
    messages: list[MessageResponse] = []


# --- Chat ---
class ChatRequest(BaseModel):
    conversation_id: str
    question: str
    llm_model: str | None = None  # 런타임 모델 오버라이드; None이면 챗봇 설정 사용


class ReferenceInfo(BaseModel):
    source: str
    page: int | None = None
    content: str
    full_content: str | None = None
    distance: float | None = None


class ChatResponse(BaseModel):
    answer: str
    references: list[ReferenceInfo]
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
