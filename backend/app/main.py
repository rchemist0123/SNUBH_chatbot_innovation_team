import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, UploadFile, File, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .auth import create_access_token, get_current_user, hash_password, verify_password
from .config import settings
from .database import Base, engine, get_db
from .models import Chatbot, Conversation, Message, User
from .rag import rag_pipeline
from .schemas import (
    ChatbotResponse,
    ChatRequest,
    ChatResponse,
    ConversationCreate,
    ConversationResponse,
    ConversationWithMessages,
    LoginRequest,
    Token,
    UserCreate,
    UserResponse,
)

logger = logging.getLogger(__name__)

# Create tables
Base.metadata.create_all(bind=engine)


# ──────────────────────────── Startup ────────────────────────────

def _seed_chatbot():
    """Register this service as a chatbot row and auto-ingest manuals."""
    from .database import SessionLocal

    db = SessionLocal()
    try:
        chatbot = db.query(Chatbot).filter(
            Chatbot.collection_name == settings.COLLECTION_NAME
        ).first()

        if not chatbot:
            chatbot = Chatbot(
                name=settings.SERVICE_NAME,
                description=settings.SERVICE_DESCRIPTION,
                collection_name=settings.COLLECTION_NAME,
            )
            db.add(chatbot)
            db.commit()
            db.refresh(chatbot)
            logger.info("Chatbot registered: %s (%s)", chatbot.name, chatbot.collection_name)
        else:
            chatbot.name = settings.SERVICE_NAME
            chatbot.description = settings.SERVICE_DESCRIPTION
            db.commit()
            logger.info("Chatbot updated: %s (%s)", chatbot.name, chatbot.collection_name)

        # Auto-ingest manuals if directory exists and collection is empty
        manuals_dir = settings.MANUALS_DIR
        if os.path.isdir(manuals_dir):
            pdf_files = [f for f in os.listdir(manuals_dir) if f.lower().endswith(".pdf")]
            if pdf_files:
                collection = rag_pipeline.chroma_client.get_or_create_collection(
                    name=settings.COLLECTION_NAME
                )
                if collection.count() == 0:
                    logger.info("Ingesting %d PDFs from %s ...", len(pdf_files), manuals_dir)
                    total = rag_pipeline.ingest_directory(manuals_dir, settings.COLLECTION_NAME)
                    logger.info("Ingested %d chunks.", total)
                else:
                    logger.info(
                        "Collection '%s' already has %d documents, skipping ingestion.",
                        settings.COLLECTION_NAME,
                        collection.count(),
                    )
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _seed_chatbot()
    yield


app = FastAPI(title="Hospital RAG Chatbot API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────── Auth ────────────────────────────

@app.post("/api/auth/register", response_model=UserResponse)
def register(body: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=400, detail="이미 존재하는 사용자명입니다.")
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="이미 존재하는 이메일입니다.")
    user = User(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/api/auth/login", response_model=Token)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="사용자명 또는 비밀번호가 올바르지 않습니다.")
    token = create_access_token({"sub": user.id})
    return Token(access_token=token)


@app.get("/api/auth/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user


# ──────────────────────────── Chatbots (read-only) ────────────────────────────

@app.get("/api/chatbots", response_model=list[ChatbotResponse])
def list_chatbots(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Chatbot).all()


# ──────────────────────────── PDF Ingestion ────────────────────────────

@app.post("/api/chatbots/{chatbot_id}/ingest")
def ingest_pdfs(
    chatbot_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    chatbot = db.query(Chatbot).filter(Chatbot.id == chatbot_id).first()
    if not chatbot:
        raise HTTPException(status_code=404, detail="챗봇을 찾을 수 없습니다.")
    manuals_dir = settings.MANUALS_DIR
    if not os.path.isdir(manuals_dir):
        os.makedirs(manuals_dir, exist_ok=True)
        raise HTTPException(
            status_code=400,
            detail=f"매뉴얼 디렉토리에 PDF를 추가해주세요: {manuals_dir}",
        )
    total = rag_pipeline.ingest_directory(manuals_dir, chatbot.collection_name)
    return {"message": f"{total}개 청크가 색인되었습니다.", "chunks": total}


@app.post("/api/chatbots/{chatbot_id}/upload")
def upload_pdf(
    chatbot_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    chatbot = db.query(Chatbot).filter(Chatbot.id == chatbot_id).first()
    if not chatbot:
        raise HTTPException(status_code=404, detail="챗봇을 찾을 수 없습니다.")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드할 수 있습니다.")

    manuals_dir = settings.MANUALS_DIR
    os.makedirs(manuals_dir, exist_ok=True)
    filepath = os.path.join(manuals_dir, file.filename)
    with open(filepath, "wb") as f:
        f.write(file.file.read())

    count = rag_pipeline.ingest_pdf(filepath, chatbot.collection_name)
    return {"message": f"{file.filename}: {count}개 청크가 색인되었습니다.", "chunks": count}


# ──────────────────────────── Conversations ────────────────────────────

@app.post("/api/conversations", response_model=ConversationResponse)
def create_conversation(
    body: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    chatbot = db.query(Chatbot).filter(Chatbot.id == body.chatbot_id).first()
    if not chatbot:
        raise HTTPException(status_code=404, detail="챗봇을 찾을 수 없습니다.")
    conv = Conversation(
        user_id=current_user.id,
        chatbot_id=body.chatbot_id,
        title=body.title or "새 대화",
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


@app.get("/api/conversations", response_model=list[ConversationResponse])
def list_conversations(
    chatbot_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Conversation).filter(Conversation.user_id == current_user.id)
    if chatbot_id:
        query = query.filter(Conversation.chatbot_id == chatbot_id)
    return query.order_by(Conversation.updated_at.desc()).all()


@app.get("/api/conversations/{conversation_id}", response_model=ConversationWithMessages)
def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conv = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == current_user.id)
        .first()
    )
    if not conv:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다.")
    return conv


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conv = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == current_user.id)
        .first()
    )
    if not conv:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다.")
    db.query(Message).filter(Message.conversation_id == conversation_id).delete()
    db.delete(conv)
    db.commit()
    return {"message": "대화가 삭제되었습니다."}


# ──────────────────────────── Chat (RAG) ────────────────────────────

@app.post("/api/chat", response_model=ChatResponse)
def chat(
    body: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conv = (
        db.query(Conversation)
        .filter(Conversation.id == body.conversation_id, Conversation.user_id == current_user.id)
        .first()
    )
    if not conv:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다.")

    chatbot = db.query(Chatbot).filter(Chatbot.id == conv.chatbot_id).first()
    if not chatbot:
        raise HTTPException(status_code=404, detail="챗봇을 찾을 수 없습니다.")
    if not chatbot.collection_name or not chatbot.collection_name.strip():
        raise HTTPException(
            status_code=400,
            detail="챗봇에 컬렉션이 설정되지 않았습니다. 먼저 PDF를 업로드해주세요.",
        )

    # Save user message
    user_msg = Message(
        conversation_id=conv.id,
        role="user",
        content=body.question,
    )
    db.add(user_msg)

    # RAG answer
    result = rag_pipeline.answer(body.question, chatbot.collection_name)

    # Save assistant message
    assistant_msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content=result["answer"],
        prompt_tokens=result["prompt_tokens"],
        completion_tokens=result["completion_tokens"],
        total_tokens=result["total_tokens"],
        latency_ms=result["latency_ms"],
        references=json.dumps(result["references"], ensure_ascii=False),
    )
    db.add(assistant_msg)

    # Update conversation title from first question
    if conv.title == "새 대화":
        conv.title = body.question[:50]

    conv.updated_at = datetime.utcnow()
    db.commit()

    return ChatResponse(
        answer=result["answer"],
        references=result["references"],
        prompt_tokens=result["prompt_tokens"],
        completion_tokens=result["completion_tokens"],
        total_tokens=result["total_tokens"],
        latency_ms=result["latency_ms"],
    )


# ──────────────────────────── Debug ────────────────────────────

@app.get("/api/debug/vectordb")
def debug_vectordb():
    """Diagnostic endpoint: check vector DB collections and document counts."""
    try:
        collections = rag_pipeline.chroma_client.list_collections()
        result = []
        for col in collections:
            collection = rag_pipeline.chroma_client.get_collection(col.name)
            count = collection.count()
            sample = collection.peek(limit=3) if count > 0 else {}
            result.append({
                "name": col.name,
                "count": count,
                "sample_ids": (sample.get("ids") or [])[:3],
                "sample_documents": [
                    d[:200] if d else "" for d in (sample.get("documents") or [])[:3]
                ],
                "sample_metadatas": (sample.get("metadatas") or [])[:3],
            })
        return {"status": "ok", "collections": result}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.get("/api/debug/search")
def debug_search(q: str, collection: str = settings.COLLECTION_NAME, top_k: int = 5):
    """Test search without LLM generation. Returns raw retrieval results with distances."""
    results = rag_pipeline.search(q, collection, top_k=top_k)
    return {
        "query": q,
        "collection": collection,
        "results_count": len(results),
        "results": results,
    }


# ──────────────────────────── Health ────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok"}
