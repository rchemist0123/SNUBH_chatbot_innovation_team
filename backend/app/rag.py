import json
import logging
import os
import time

import chromadb
import httpx
import pdfplumber
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

from .config import settings

logger = logging.getLogger(__name__)


# ──────────────────────────── Embeddings ────────────────────────────


class HuggingFaceEmbeddings:
    """HuggingFace sentence-transformers embedding client.

    Uses intfloat/multilingual-e5-large by default.
    The e5 model family requires 'query: ' prefix for queries
    and 'passage: ' prefix for documents.
    """

    def __init__(
        self,
        model_name: str = settings.HF_EMBEDDING_MODEL,
        cache_dir: str = settings.HF_CACHE_DIR,
    ):
        self.model = SentenceTransformer(model_name, cache_folder=cache_dir)
        self.model_name = model_name

    def embed(self, texts: list[str], prefix: str = "passage: ") -> list[list[float]]:
        """Embed a list of texts with the given prefix."""
        prefixed = [f"{prefix}{t}" for t in texts]
        embeddings = self.model.encode(
            prefixed, show_progress_bar=False, normalize_embeddings=True
        )
        return embeddings.tolist()

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query with 'query: ' prefix."""
        return self.embed([text], prefix="query: ")[0]


# ──────────────────────────── LLM ────────────────────────────


class OllamaLLM:
    """Ollama LLM client."""

    def __init__(self, model: str = settings.LLM_MODEL, base_url: str = settings.OLLAMA_BASE_URL):
        self.model = model
        self.base_url = base_url

    def generate(self, prompt: str, temperature: float | None = None) -> dict:
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        if temperature is not None:
            payload["options"] = {"temperature": temperature}
        resp = httpx.post(
            f"{self.base_url}/api/generate",
            json=payload,
            timeout=300.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "response": data.get("response", ""),
            "prompt_eval_count": data.get("prompt_eval_count", 0),
            "eval_count": data.get("eval_count", 0),
        }

    def generate_stream(self, prompt: str, temperature: float | None = None):
        """Stream tokens from Ollama. Yields dicts with type 'token' or 'stats'."""
        payload = {"model": self.model, "prompt": prompt, "stream": True}
        if temperature is not None:
            payload["options"] = {"temperature": temperature}
        with httpx.stream(
            "POST",
            f"{self.base_url}/api/generate",
            json=payload,
            timeout=300.0,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    data = json.loads(line)
                    token = data.get("response", "")
                    if token:
                        yield {"type": "token", "content": token}
                    if data.get("done"):
                        yield {
                            "type": "stats",
                            "prompt_eval_count": data.get("prompt_eval_count", 0),
                            "eval_count": data.get("eval_count", 0),
                        }


# ──────────────────────────── PDF Parsing ────────────────────────────


def _table_to_text(table: list[list]) -> str:
    """Convert a pdfplumber table to a readable pipe-delimited text."""
    rows = []
    for row in table:
        cleaned = [str(cell).strip() if cell else "" for cell in row]
        rows.append(" | ".join(cleaned))
    return "\n".join(rows)


def load_pdf_with_tables(pdf_path: str) -> list[dict]:
    """Extract text and tables from a PDF using pdfplumber.

    Tables are extracted separately and converted to text.
    Returns a list of dicts: {"content": str, "metadata": dict}.
    """
    documents = []
    filename = os.path.basename(pdf_path)

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            # Extract tables first
            tables = page.extract_tables()
            for table in tables:
                if table:
                    table_text = _table_to_text(table)
                    if table_text.strip():
                        documents.append({
                            "content": table_text,
                            "metadata": {
                                "source": filename,
                                "page": page_num,
                                "content_type": "table",
                            },
                        })

            # Extract body text
            text = page.extract_text() or ""
            if text.strip():
                documents.append({
                    "content": text,
                    "metadata": {
                        "source": filename,
                        "page": page_num,
                        "content_type": "text",
                    },
                })

    return documents


# ──────────────────────────── RAG Pipeline ────────────────────────────


class RAGPipeline:
    """RAG pipeline: PDF ingestion, vector search, and answer generation."""

    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings()
        self.llm = OllamaLLM()
        self.chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            separators=["\n\n", "\n", ".", "!", "?", ";", ",", " ", ""],
        )

    def ingest_pdf(
        self, pdf_path: str, collection_name: str,
        chunk_size: int | None = None, chunk_overlap: int | None = None,
    ) -> int:
        """Load a PDF, split into chunks, embed, and store in ChromaDB.
        Returns the number of chunks ingested."""
        raw_docs = load_pdf_with_tables(pdf_path)

        # Use custom splitter if custom chunk settings are provided
        if chunk_size or chunk_overlap:
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size or settings.CHUNK_SIZE,
                chunk_overlap=chunk_overlap or settings.CHUNK_OVERLAP,
                separators=["\n\n", "\n", ".", "!", "?", ";", ",", " ", ""],
            )
        else:
            splitter = self.text_splitter

        chunks = []
        for doc in raw_docs:
            if doc["metadata"]["content_type"] == "table":
                chunks.append(doc)
            else:
                split_texts = splitter.split_text(doc["content"])
                for text in split_texts:
                    chunks.append({
                        "content": text,
                        "metadata": doc["metadata"].copy(),
                    })

        if not chunks:
            logger.warning("No chunks extracted from %s", pdf_path)
            return 0

        collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        texts = [chunk["content"] for chunk in chunks]
        metadatas = [chunk["metadata"] for chunk in chunks]
        ids = [f"{os.path.basename(pdf_path)}_{i}" for i in range(len(chunks))]

        # Embed in batches
        batch_size = 50
        for start in range(0, len(texts), batch_size):
            end = min(start + batch_size, len(texts))
            batch_texts = texts[start:end]
            batch_ids = ids[start:end]
            batch_metas = metadatas[start:end]
            batch_embeddings = self.embeddings.embed(batch_texts)
            collection.upsert(
                ids=batch_ids,
                documents=batch_texts,
                metadatas=batch_metas,
                embeddings=batch_embeddings,
            )

        logger.info("Ingested %d chunks from %s", len(chunks), pdf_path)
        return len(chunks)

    def ingest_directory(self, directory: str, collection_name: str) -> int:
        """Ingest all PDFs in a directory. Returns total chunks."""
        total = 0
        for filename in os.listdir(directory):
            if filename.lower().endswith(".pdf"):
                filepath = os.path.join(directory, filename)
                count = self.ingest_pdf(filepath, collection_name)
                total += count
        return total

    def search(
        self, query: str, collection_name: str,
        top_k: int | None = None, distance_threshold: float | None = None,
    ) -> list[dict]:
        """Search the vector store and return relevant chunks."""
        top_k = top_k or settings.TOP_K
        distance_threshold = distance_threshold if distance_threshold is not None else settings.DISTANCE_THRESHOLD

        collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        if collection.count() == 0:
            logger.warning("Collection '%s' is empty.", collection_name)
            return []

        query_embedding = self.embeddings.embed_query(query)

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        retrieved = []
        if results["documents"]:
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                if dist > distance_threshold:
                    continue
                retrieved.append({
                    "content": doc,
                    "source": meta.get("source", ""),
                    "page": meta.get("page"),
                    "content_type": meta.get("content_type", "text"),
                    "distance": dist,
                })
        return retrieved

    _DEFAULT_SYSTEM_PROMPT = (
        "당신은 병원 매뉴얼 전문 어시스턴트입니다.\n"
        "아래 제공된 참고 문서를 기반으로 질문에 정확하게 답변해주세요.\n"
        '답변은 반드시 참고 문서의 내용을 근거로 하며, 문서에 없는 내용은 "제공된 매뉴얼에서 해당 정보를 찾을 수 없습니다."라고 답변하세요.\n'
        "답변은 한국어로 작성하세요."
    )

    def answer(
        self, question: str, collection_name: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        top_k: int | None = None,
        distance_threshold: float | None = None,
        llm_model: str | None = None,
    ) -> dict:
        """Full RAG: retrieve context, generate answer, return with metadata."""
        start_time = time.time()

        retrieved_docs = self.search(
            question, collection_name,
            top_k=top_k, distance_threshold=distance_threshold,
        )

        if not retrieved_docs:
            latency_ms = (time.time() - start_time) * 1000
            return {
                "answer": "제공된 매뉴얼에서 해당 정보를 찾을 수 없습니다. 다른 키워드로 질문해 주세요.",
                "references": [],
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "latency_ms": latency_ms,
            }

        context = "\n\n---\n\n".join([doc["content"] for doc in retrieved_docs])
        sys_prompt = system_prompt or self._DEFAULT_SYSTEM_PROMPT

        prompt = f"""{sys_prompt}

[참고 문서]
{context}

[질문]
{question}

[답변]"""

        llm = OllamaLLM(model=llm_model) if llm_model else self.llm
        result = llm.generate(prompt, temperature=temperature)
        latency_ms = (time.time() - start_time) * 1000

        references = [
            {
                "source": doc["source"],
                "page": doc["page"],
                "content": doc["content"][:300],
                "full_content": doc["content"],
                "distance": doc.get("distance"),
            }
            for doc in retrieved_docs
        ]

        prompt_tokens = result.get("prompt_eval_count", 0)
        completion_tokens = result.get("eval_count", 0)

        return {
            "answer": result["response"],
            "references": references,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "latency_ms": latency_ms,
        }


    def answer_stream(
        self, question: str, collection_name: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        top_k: int | None = None,
        distance_threshold: float | None = None,
        llm_model: str | None = None,
    ):
        """Full RAG: retrieve context, then stream the answer token by token.

        Yields dicts:
          {"type": "token", "content": str}
          {"type": "meta", "references": [...], "prompt_tokens": int,
           "completion_tokens": int, "total_tokens": int, "latency_ms": float}
        """
        start_time = time.time()
        retrieved_docs = self.search(
            question, collection_name,
            top_k=top_k, distance_threshold=distance_threshold,
        )

        if not retrieved_docs:
            latency_ms = (time.time() - start_time) * 1000
            no_result_text = "제공된 매뉴얼에서 해당 정보를 찾을 수 없습니다. 다른 키워드로 질문해 주세요."
            yield {"type": "token", "content": no_result_text}
            yield {
                "type": "meta",
                "answer": no_result_text,
                "references": [],
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "latency_ms": latency_ms,
            }
            return

        context = "\n\n---\n\n".join([doc["content"] for doc in retrieved_docs])
        sys_prompt = system_prompt or self._DEFAULT_SYSTEM_PROMPT

        prompt = f"""{sys_prompt}

[참고 문서]
{context}

[질문]
{question}

[답변]"""

        references = [
            {
                "source": doc["source"],
                "page": doc["page"],
                "content": doc["content"][:300],
                "full_content": doc["content"],
                "distance": doc.get("distance"),
            }
            for doc in retrieved_docs
        ]

        llm = OllamaLLM(model=llm_model) if llm_model else self.llm
        for chunk in llm.generate_stream(prompt, temperature=temperature):
            if chunk["type"] == "token":
                yield chunk
            elif chunk["type"] == "stats":
                latency_ms = (time.time() - start_time) * 1000
                prompt_tokens = chunk["prompt_eval_count"]
                completion_tokens = chunk["eval_count"]
                yield {
                    "type": "meta",
                    "references": references,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                    "latency_ms": latency_ms,
                }


# Singleton
rag_pipeline = RAGPipeline()
