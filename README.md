# 병원 매뉴얼 RAG 챗봇

병원 매뉴얼 PDF를 기반으로 질문에 답변하는 RAG(Retrieval-Augmented Generation) 챗봇 시스템입니다.

## 아키텍처

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│  Streamlit   │────▶│  FastAPI Backend  │────▶│   Ollama     │
│  Frontend    │◀────│                  │◀────│  (LLM/Embed) │
└─────────────┘     │  ┌────────────┐  │     └─────────────┘
                    │  │  SQLite DB  │  │
                    │  │ (사용자/대화) │  │
                    │  └────────────┘  │
                    │  ┌────────────┐  │
                    │  │  ChromaDB   │  │
                    │  │ (벡터 검색)  │  │
                    │  └────────────┘  │
                    └──────────────────┘
```

## 주요 기능

- **사용자 인증**: 회원가입 / 로그인 (JWT 기반)
- **PDF 매뉴얼 관리**: PDF 업로드 → 청크 분할 → 임베딩 → ChromaDB 저장
- **RAG 기반 질의응답**: 벡터 검색 → 관련 문서 검색 → Ollama LLM으로 답변 생성
- **대화 기록 관리**: 대화별 메시지 저장, 토큰 사용량/응답 시간 기록
- **다중 챗봇 지원**: 챗봇별 독립된 벡터 컬렉션, 네비게이션으로 챗봇 전환
- **참고 문서 표시**: 답변 근거가 된 원문 출처 및 페이지 번호 표시

## 사전 요구사항

- Python 3.11+
- [Ollama](https://ollama.ai/) 설치 및 실행 중
- 필요한 Ollama 모델:
  ```bash
  ollama pull llama3
  ollama pull nomic-embed-text
  ```

## 설치 및 실행

### 1. Backend

```bash
cd backend
pip install -r requirements.txt

# .env 파일 생성 (선택)
cat > .env << EOF
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=llama3
EMBEDDING_MODEL=nomic-embed-text
EOF

# 서버 실행
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Frontend

```bash
cd frontend
pip install -r requirements.txt

# 실행
streamlit run app.py --server.port 8501
```

### 3. 사용 방법

1. 브라우저에서 `http://localhost:8501` 접속
2. 회원가입 후 로그인
3. 사이드바에서 챗봇 생성 (이름, 설명, 컬렉션명 입력)
4. PDF 매뉴얼 업로드 (자동으로 임베딩 및 색인)
5. "새 대화" 생성 후 질문 입력

## 프로젝트 구조

```
├── backend/
│   ├── app/
│   │   ├── main.py        # FastAPI 엔드포인트
│   │   ├── auth.py        # JWT 인증
│   │   ├── models.py      # SQLAlchemy DB 모델
│   │   ├── schemas.py     # Pydantic 스키마
│   │   ├── database.py    # DB 연결 설정
│   │   ├── config.py      # 환경 설정
│   │   └── rag.py         # RAG 파이프라인 (임베딩, 검색, 생성)
│   ├── data/manuals/      # PDF 매뉴얼 저장 경로
│   └── requirements.txt
├── frontend/
│   ├── app.py             # Streamlit UI
│   ├── api_client.py      # Backend API 클라이언트
│   ├── .streamlit/
│   │   └── config.toml    # 파란색 테마 설정
│   └── requirements.txt
└── README.md
```

## 환경 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `DATABASE_URL` | `sqlite:///./chatbot.db` | SQLite DB 경로 |
| `SECRET_KEY` | (변경 필요) | JWT 시크릿 키 |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama 서버 주소 |
| `LLM_MODEL` | `llama3` | 답변 생성 모델 |
| `EMBEDDING_MODEL` | `nomic-embed-text` | 임베딩 모델 |
| `CHUNK_SIZE` | `1000` | 문서 청크 크기 |
| `CHUNK_OVERLAP` | `200` | 청크 오버랩 |
| `TOP_K` | `5` | 검색 결과 수 |

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/auth/register` | 회원가입 |
| POST | `/api/auth/login` | 로그인 |
| GET | `/api/auth/me` | 현재 사용자 정보 |
| GET | `/api/chatbots` | 챗봇 목록 |
| POST | `/api/chatbots` | 챗봇 생성 |
| POST | `/api/chatbots/{id}/upload` | PDF 업로드 |
| POST | `/api/chatbots/{id}/ingest` | 디렉토리 PDF 색인 |
| GET | `/api/conversations` | 대화 목록 |
| POST | `/api/conversations` | 대화 생성 |
| GET | `/api/conversations/{id}` | 대화 상세 (메시지 포함) |
| DELETE | `/api/conversations/{id}` | 대화 삭제 |
| POST | `/api/chat` | RAG 질의응답 |
