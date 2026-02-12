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
    collection_name: str


class ChatbotResponse(BaseModel):
    id: str
    name: str
    description: str | None
    collection_name: str
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


class ReferenceInfo(BaseModel):
    source: str
    page: int | None = None
    content: str


class ChatResponse(BaseModel):
    answer: str
    references: list[ReferenceInfo]
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
