import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base


def generate_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversations = relationship("Conversation", back_populates="user")


class Chatbot(Base):
    __tablename__ = "chatbots"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    collection_name = Column(String(100), unique=True, nullable=False)
    icon = Column(String(10), nullable=True, default="🤖")
    creator_id = Column(String, ForeignKey("users.id"), nullable=True)  # NULL = system chatbot
    system_prompt = Column(Text, nullable=True)
    temperature = Column(Float, nullable=True, default=0.7)
    top_k = Column(Integer, nullable=True, default=5)
    distance_threshold = Column(Float, nullable=True, default=0.4)
    chunk_size = Column(Integer, nullable=True, default=500)
    chunk_overlap = Column(Integer, nullable=True, default=100)
    created_at = Column(DateTime, default=datetime.utcnow)

    creator = relationship("User", foreign_keys=[creator_id])
    conversations = relationship("Conversation", back_populates="chatbot")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=generate_uuid)
    title = Column(String(200), nullable=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    chatbot_id = Column(String, ForeignKey("chatbots.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="conversations")
    chatbot = relationship("Chatbot", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=generate_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    latency_ms = Column(Float, default=0.0)
    references = Column(Text, nullable=True)  # JSON string of source references
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")
