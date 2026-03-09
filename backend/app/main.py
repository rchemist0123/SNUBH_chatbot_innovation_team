import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, UploadFile, File, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .auth import create_access_token, get_current_user, hash_password, verify_password
from .config import settings
from .database import Base, engine, get_db, SessionLocal
from .models import Chatbot, Conversation, Message, User
from .rag import rag_pipeline
from .schemas import (
    ChatbotCreate,
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


# ──────────────────────────── DB Migration ────────────────────────────

def _migrate_chatbots_table():
    """Add new columns to the chatbots table if they don't exist yet.

    SQLAlchemy's create_all() only creates new tables — it does NOT alter
    existing ones.  This lightweight migration inspects the live schema and
    adds any missing columns so that the app works with databases created
    before the custom-chatbot feature was introduced.
    """
    from sqlalchemy import inspect as sa_inspect, text

    inspector = sa_inspect(engine)
    existing = {col["name"] for col in inspector.get_columns("chatbots")}

    # (column_name, SQL type, default_value)
    new_columns = [
        ("icon", "VARCHAR(10)", "'🤖'"),
        ("creator_id", "VARCHAR", "NULL"),
        ("system_prompt", "TEXT", "NULL"),
        ("temperature", "FLOAT", "0.7"),
        ("top_k", "INTEGER", "5"),
        ("distance_threshold", "FLOAT", "0.4"),
        ("chunk_size", "INTEGER", "500"),
        ("chunk_overlap", "INTEGER", "100"),
        ("llm_model", "VARCHAR(100)", "NULL"),
    ]

    with engine.begin() as conn:
        for col_name, col_type, default in new_columns:
            if col_name not in existing:
                stmt = f"ALTER TABLE chatbots ADD COLUMN {col_name} {col_type} DEFAULT {default}"
                conn.execute(text(stmt))
                logger.info("Migrated chatbots table: added column '%s'", col_name)


_migrate_chatbots_table()


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
            # Check if a legacy chatbot with the same name exists (different collection_name)
            legacy = db.query(Chatbot).filter(
                Chatbot.name == settings.SERVICE_NAME
            ).first()
            if legacy:
                # Migrate: update collection_name in-place to avoid creating a duplicate
                legacy.collection_name = settings.COLLECTION_NAME
                legacy.description = settings.SERVICE_DESCRIPTION
                db.commit()
                db.refresh(legacy)
                chatbot = legacy
                logger.info("Chatbot migrated: %s (%s)", chatbot.name, chatbot.collection_name)
            else:
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

        # Cleanup: remove duplicate *system* chatbot entries (creator_id IS NULL)
        # that are not the canonical one. User-created chatbots are preserved.
        duplicates = (
            db.query(Chatbot)
            .filter(Chatbot.id != chatbot.id, Chatbot.creator_id.is_(None))
            .all()
        )
        if duplicates:
            for dup in duplicates:
                logger.warning(
                    "Removing duplicate system chatbot: id=%s name=%s collection=%s",
                    dup.id, dup.name, dup.collection_name,
                )
                db.query(Conversation).filter(
                    Conversation.chatbot_id == dup.id
                ).update({"chatbot_id": chatbot.id}, synchronize_session=False)
                db.delete(dup)
            db.commit()
            logger.info("Removed %d duplicate system chatbot(s).", len(duplicates))

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


# ──────────────────────────── Chatbots ────────────────────────────

@app.get("/api/chatbots", response_model=list[ChatbotResponse])
def list_chatbots(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Chatbot).all()


def _sanitize_collection_name(name: str) -> str:
    """Create a valid ChromaDB collection name from a chatbot name."""
    import re
    import uuid as _uuid
    # Replace non-alphanumeric with underscores, prefix to ensure validity
    sanitized = re.sub(r"[^a-zA-Z0-9가-힣_]", "_", name).strip("_")
    if not sanitized:
        sanitized = "custom"
    # Append short UUID to ensure uniqueness
    short_id = _uuid.uuid4().hex[:8]
    return f"custom_{sanitized}_{short_id}"


@app.post("/api/chatbots", response_model=ChatbotResponse)
def create_chatbot(
    body: ChatbotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    collection_name = _sanitize_collection_name(body.name)
    chatbot = Chatbot(
        name=body.name,
        description=body.description,
        collection_name=collection_name,
        icon=body.icon or "🤖",
        creator_id=current_user.id,
        llm_model=body.llm_model,
        system_prompt=body.system_prompt,
        temperature=body.temperature,
        top_k=body.top_k,
        distance_threshold=body.distance_threshold,
        chunk_size=body.chunk_size,
        chunk_overlap=body.chunk_overlap,
    )
    db.add(chatbot)
    db.commit()
    db.refresh(chatbot)

    # Create the ChromaDB collection eagerly
    rag_pipeline.chroma_client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )

    logger.info("Custom chatbot created: %s by user %s", chatbot.name, current_user.id)
    return chatbot


@app.delete("/api/chatbots/{chatbot_id}")
def delete_chatbot(
    chatbot_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    chatbot = db.query(Chatbot).filter(Chatbot.id == chatbot_id).first()
    if not chatbot:
        raise HTTPException(status_code=404, detail="챗봇을 찾을 수 없습니다.")
    if chatbot.creator_id is None:
        raise HTTPException(status_code=403, detail="시스템 챗봇은 삭제할 수 없습니다.")
    if chatbot.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="본인이 만든 챗봇만 삭제할 수 있습니다.")

    # Delete associated conversations and messages
    conversations = db.query(Conversation).filter(Conversation.chatbot_id == chatbot_id).all()
    for conv in conversations:
        db.query(Message).filter(Message.conversation_id == conv.id).delete()
        db.delete(conv)

    # Delete ChromaDB collection
    try:
        rag_pipeline.chroma_client.delete_collection(chatbot.collection_name)
    except Exception as e:
        logger.warning("Failed to delete ChromaDB collection %s: %s", chatbot.collection_name, e)

    # Delete uploaded files
    chatbot_data_dir = os.path.join(settings.MANUALS_DIR, chatbot.collection_name)
    if os.path.isdir(chatbot_data_dir):
        import shutil
        shutil.rmtree(chatbot_data_dir, ignore_errors=True)

    db.delete(chatbot)
    db.commit()
    logger.info("Custom chatbot deleted: %s by user %s", chatbot.name, current_user.id)
    return {"message": "챗봇이 삭제되었습니다."}


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
    # Use per-chatbot directory for custom chatbots, global for system chatbot
    if chatbot.creator_id:
        manuals_dir = os.path.join(settings.MANUALS_DIR, chatbot.collection_name)
    else:
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

    # Use per-chatbot directory for custom chatbots
    if chatbot.creator_id:
        manuals_dir = os.path.join(settings.MANUALS_DIR, chatbot.collection_name)
    else:
        manuals_dir = settings.MANUALS_DIR
    os.makedirs(manuals_dir, exist_ok=True)
    filepath = os.path.join(manuals_dir, file.filename)
    with open(filepath, "wb") as f:
        f.write(file.file.read())

    # Use chatbot-specific chunk settings if available
    chunk_size = chatbot.chunk_size or settings.CHUNK_SIZE
    chunk_overlap = chatbot.chunk_overlap or settings.CHUNK_OVERLAP
    count = rag_pipeline.ingest_pdf(
        filepath, chatbot.collection_name,
        chunk_size=chunk_size, chunk_overlap=chunk_overlap,
    )
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

    # RAG answer with chatbot-specific settings
    result = rag_pipeline.answer(
        body.question,
        chatbot.collection_name,
        system_prompt=chatbot.system_prompt,
        temperature=chatbot.temperature,
        top_k=chatbot.top_k,
        distance_threshold=chatbot.distance_threshold,
        llm_model=chatbot.llm_model,
    )

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


@app.post("/api/chat/stream")
def chat_stream_endpoint(
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

    conv_id = conv.id
    chatbot_collection = chatbot.collection_name
    chatbot_system_prompt = chatbot.system_prompt
    chatbot_temperature = chatbot.temperature
    chatbot_top_k = chatbot.top_k
    chatbot_distance_threshold = chatbot.distance_threshold
    chatbot_llm_model = chatbot.llm_model

    # Save user message before streaming starts
    user_msg = Message(
        conversation_id=conv_id,
        role="user",
        content=body.question,
    )
    db.add(user_msg)
    if conv.title == "새 대화":
        conv.title = body.question[:50]
    conv.updated_at = datetime.utcnow()
    db.commit()

    def generate():
        full_answer_parts = []
        final_meta = {
            "references": [],
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "latency_ms": 0,
        }

        try:
            for chunk in rag_pipeline.answer_stream(
                body.question, chatbot_collection,
                system_prompt=chatbot_system_prompt,
                temperature=chatbot_temperature,
                top_k=chatbot_top_k,
                distance_threshold=chatbot_distance_threshold,
                llm_model=chatbot_llm_model,
            ):
                if chunk["type"] == "token":
                    full_answer_parts.append(chunk["content"])
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk['content']}, ensure_ascii=False)}\n\n"
                elif chunk["type"] == "meta":
                    final_meta = {k: v for k, v in chunk.items() if k != "type"}
                    yield f"data: {json.dumps({'type': 'meta', **final_meta}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error("Streaming error: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

        # Save assistant message to DB using a new session (original is closed after endpoint returns)
        answer = "".join(full_answer_parts)
        save_db = SessionLocal()
        try:
            assistant_msg = Message(
                conversation_id=conv_id,
                role="assistant",
                content=answer,
                prompt_tokens=final_meta["prompt_tokens"],
                completion_tokens=final_meta["completion_tokens"],
                total_tokens=final_meta["total_tokens"],
                latency_ms=final_meta["latency_ms"],
                references=json.dumps(final_meta.get("references", []), ensure_ascii=False),
            )
            save_db.add(assistant_msg)
            save_db.commit()
        except Exception as e:
            logger.error("DB save error after stream: %s", e)
        finally:
            save_db.close()

        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


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

@app.get("/api/ollama/models")
def list_ollama_models(_: User = Depends(get_current_user)):
    """Ollama 서버에서 사용 가능한 모델 목록을 반환합니다."""
    import httpx
    try:
        resp = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        models = [
            {
                "name": m["name"],
                "size": m.get("size", 0),
                "modified_at": m.get("modified_at", ""),
            }
            for m in data.get("models", [])
        ]
        return {"models": models, "default": settings.LLM_MODEL}
    except Exception as e:
        logger.warning("Failed to fetch Ollama models: %s", e)
        return {"models": [{"name": settings.LLM_MODEL, "size": 0, "modified_at": ""}], "default": settings.LLM_MODEL}


@app.get("/api/health")
def health():
    return {"status": "ok"}
