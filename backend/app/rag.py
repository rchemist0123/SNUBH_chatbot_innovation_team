import json
import os
import time

import chromadb
import httpx
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .config import settings


class OllamaEmbeddings:
    """Ollama embedding client."""

    def __init__(self, model: str = settings.EMBEDDING_MODEL, base_url: str = settings.OLLAMA_BASE_URL):
        self.model = model
        self.base_url = base_url

    def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings = []
        for text in texts:
            resp = httpx.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=120.0,
            )
            resp.raise_for_status()
            embeddings.append(resp.json()["embedding"])
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text])[0]


class OllamaLLM:
    """Ollama LLM client."""

    def __init__(self, model: str = settings.LLM_MODEL, base_url: str = settings.OLLAMA_BASE_URL):
        self.model = model
        self.base_url = base_url

    def generate(self, prompt: str) -> dict:
        resp = httpx.post(
            f"{self.base_url}/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": False},
            timeout=300.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "response": data.get("response", ""),
            "prompt_eval_count": data.get("prompt_eval_count", 0),
            "eval_count": data.get("eval_count", 0),
        }


class RAGPipeline:
    """RAG pipeline: PDF ingestion, vector search, and answer generation."""

    def __init__(self):
        self.embeddings = OllamaEmbeddings()
        self.llm = OllamaLLM()
        self.chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )

    def ingest_pdf(self, pdf_path: str, collection_name: str) -> int:
        """Load a PDF, split into chunks, embed, and store in ChromaDB.
        Returns the number of chunks ingested."""
        loader = PyPDFLoader(pdf_path)
        pages = loader.load()
        chunks = self.text_splitter.split_documents(pages)

        collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        texts = [chunk.page_content for chunk in chunks]
        metadatas = [
            {
                "source": os.path.basename(pdf_path),
                "page": chunk.metadata.get("page", 0),
            }
            for chunk in chunks
        ]
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

    def search(self, query: str, collection_name: str, top_k: int = settings.TOP_K) -> list[dict]:
        """Search the vector store and return relevant chunks."""
        collection = self.chroma_client.get_or_create_collection(name=collection_name)
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
                retrieved.append({
                    "content": doc,
                    "source": meta.get("source", ""),
                    "page": meta.get("page"),
                    "distance": dist,
                })
        return retrieved

    def answer(self, question: str, collection_name: str) -> dict:
        """Full RAG: retrieve context, generate answer, return with metadata."""
        start_time = time.time()

        # Retrieve
        retrieved_docs = self.search(question, collection_name)
        context = "\n\n---\n\n".join([doc["content"] for doc in retrieved_docs])

        # Build prompt
        prompt = f"""당신은 병원 매뉴얼 전문 어시스턴트입니다.
아래 제공된 참고 문서를 기반으로 질문에 정확하게 답변해주세요.
답변은 반드시 참고 문서의 내용을 근거로 하며, 문서에 없는 내용은 "제공된 매뉴얼에서 해당 정보를 찾을 수 없습니다."라고 답변하세요.
답변은 한국어로 작성하세요.

[참고 문서]
{context}

[질문]
{question}

[답변]"""

        # Generate
        result = self.llm.generate(prompt)
        latency_ms = (time.time() - start_time) * 1000

        references = [
            {
                "source": doc["source"],
                "page": doc["page"],
                "content": doc["content"][:300],
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


# Singleton
rag_pipeline = RAGPipeline()
