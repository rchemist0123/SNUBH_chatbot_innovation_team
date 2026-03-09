import json

import streamlit as st
import streamlit.components.v1 as components

from api_client import APIClient

# ──────────────────────────── Page Config ────────────────────────────

st.set_page_config(
    page_title="병원 매뉴얼 RAG 챗봇",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────── Custom CSS ────────────────────────────

st.markdown("""
<style>
    /* Blue theme overrides */
    .stApp {
        background-color: #FAFBFE;
    }

    /* Header bar */
    .main-header {
        background: linear-gradient(135deg, #1565C0, #1976D2);
        color: white;
        padding: 0.8rem 1.5rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .main-header h2 {
        margin: 0;
        color: white;
    }

    /* Chat messages */
    .user-message-wrapper {
        display: flex;
        justify-content: flex-end;
        margin: 8px 0;
    }
    .user-message {
        background-color: #1565C0;
        color: white;
        padding: 12px 18px;
        border-radius: 18px 18px 4px 18px;
        max-width: 80%;
        display: inline-block;
        text-align: left;
        word-break: break-word;
    }
    .assistant-message {
        background-color: #FFFFFF;
        color: #1a1a1a;
        padding: 12px 18px;
        border-radius: 18px 18px 18px 4px;
        margin: 8px 0;
        max-width: 80%;
        border: 1px solid #E0E0E0;
    }

    /* Loading indicator */
    .loading-indicator {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 12px 18px;
        background-color: #FFFFFF;
        color: #555555;
        border-radius: 18px 18px 18px 4px;
        margin: 8px 0;
        max-width: 80%;
        border: 1px solid #E0E0E0;
        font-size: 0.9rem;
    }
    .spinner-dots {
        display: inline-flex;
        gap: 5px;
        align-items: center;
    }
    .spinner-dots span {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background-color: #1565C0;
        animation: dot-bounce 1.2s infinite ease-in-out;
    }
    .spinner-dots span:nth-child(1) { animation-delay: 0s; }
    .spinner-dots span:nth-child(2) { animation-delay: 0.2s; }
    .spinner-dots span:nth-child(3) { animation-delay: 0.4s; }
    @keyframes dot-bounce {
        0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
        40% { transform: scale(1.0); opacity: 1; }
    }

    /* Reference card */
    .ref-card {
        background-color: #FFFFFF;
        border: 1px solid #E0E0E0;
        border-left: 4px solid #90CAF9;
        padding: 10px 14px;
        border-radius: 6px;
        margin: 6px 0;
        font-size: 0.85rem;
        color: #1a1a1a;
    }
    .ref-card .ref-source {
        font-weight: bold;
        color: #333333;
    }
    .ref-score {
        display: inline-block;
        background: linear-gradient(135deg, #1565C0, #42A5F5);
        color: white;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-left: 8px;
        vertical-align: middle;
    }
    .ref-rank {
        display: inline-block;
        background-color: #E3F2FD;
        color: #1565C0;
        padding: 1px 7px;
        border-radius: 10px;
        font-size: 0.72rem;
        font-weight: 700;
        margin-right: 6px;
        vertical-align: middle;
    }
    .ref-content-preview {
        color: #555;
        margin-top: 6px;
        line-height: 1.4;
        display: -webkit-box;
        -webkit-line-clamp: 3;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }

    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #E3F2FD;
    }
    section[data-testid="stSidebar"] .stButton > button {
        width: 100%;
        text-align: left;
        background-color: transparent;
        border: 1px solid #90CAF9;
        color: #0D47A1;
        border-radius: 8px;
        margin-bottom: 4px;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        background-color: #BBDEFB;
    }

    /* Token info */
    .token-info {
        font-size: 0.75rem;
        color: #78909C;
        text-align: right;
        margin-top: 2px;
    }

    /* Chatbot card buttons - primary buttons styled as cards */
    .stButton > button[kind="primary"] {
        background: white !important;
        border: 2px solid #90CAF9 !important;
        border-radius: 16px !important;
        padding: 28px 20px !important;
        min-height: 160px !important;
        color: #0D47A1 !important;
        font-size: 1rem !important;
        font-weight: 600 !important;
        transition: all 0.2s !important;
        white-space: pre-wrap !important;
        line-height: 2 !important;
        text-align: center !important;
    }
    .stButton > button[kind="primary"]:hover {
        border-color: #1565C0 !important;
        box-shadow: 0 4px 16px rgba(21, 101, 192, 0.18) !important;
        transform: translateY(-2px) !important;
        background: #E3F2FD !important;
        color: #0D47A1 !important;
    }

    /* Centered section title */
    .section-title {
        text-align: center;
        color: #1565C0;
        font-size: 1.2rem;
        font-weight: 600;
        margin: 1.5rem 0 0.5rem;
    }
    .section-divider {
        border: none;
        border-top: 2px solid #E3F2FD;
        margin: 0.5rem 0 1.5rem;
    }

    /* Bottom padding so fixed chat input doesn't overlap content */
    .main .block-container {
        padding-bottom: 80px;
    }

    /* Chat & reference panels: equal viewport-responsive height */
    .stMainBlockContainer [data-testid="stColumn"] [data-testid="stVerticalBlockBorderWrapper"] {
        height: calc(100vh - 260px) !important;
        min-height: 400px !important;
    }
    .stMainBlockContainer [data-testid="stColumn"] [data-testid="stVerticalBlockBorderWrapper"] > div {
        height: 100% !important;
        max-height: 100% !important;
    }

    /* Auth page: don't force viewport height on auth columns */
    .stMainBlockContainer [data-testid="stColumn"]:has(.auth-card) [data-testid="stVerticalBlockBorderWrapper"],
    .stMainBlockContainer [data-testid="stColumn"]:has(.main-header) [data-testid="stVerticalBlockBorderWrapper"] {
        height: auto !important;
        min-height: auto !important;
    }
    .stMainBlockContainer [data-testid="stColumn"]:has(.auth-card) [data-testid="stVerticalBlockBorderWrapper"] > div,
    .stMainBlockContainer [data-testid="stColumn"]:has(.main-header) [data-testid="stVerticalBlockBorderWrapper"] > div {
        height: auto !important;
        max-height: none !important;
    }

    /* Auth form card */
    .auth-card {
        background: white;
        border: 1px solid #BBDEFB;
        border-radius: 16px;
        padding: 2rem 2rem 1.5rem;
        box-shadow: 0 4px 20px rgba(21, 101, 192, 0.08);
        margin-top: 1rem;
    }

    /* Create chatbot card - dashed border style */
    .create-chatbot-card {
        border: 2px dashed #90CAF9 !important;
        background: #F5F9FF !important;
    }
    .create-chatbot-card:hover {
        border-color: #1565C0 !important;
        background: #E3F2FD !important;
    }

    /* Delete button for custom chatbots */
    .chatbot-delete-btn {
        position: absolute;
        top: 8px;
        right: 8px;
        background: rgba(0,0,0,0.05);
        border: none;
        border-radius: 50%;
        width: 28px;
        height: 28px;
        cursor: pointer;
        font-size: 0.8rem;
    }

    /* ── Conversation history items (buttons inside columns in sidebar) ── */
    section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {
        gap: 0 !important;
        margin-bottom: 2px !important;
    }
    section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] .stButton > button {
        border: none !important;
        background: transparent !important;
        padding: 6px 10px !important;
        margin: 0 !important;
        border-radius: 6px !important;
        font-size: 0.85rem !important;
        min-height: 0 !important;
        height: auto !important;
        line-height: 1.4 !important;
        text-align: left !important;
        justify-content: flex-start !important;
    }
    section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] .stButton > button > div {
        width: 100% !important;
        text-align: left !important;
    }
    section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] .stButton > button > div > p {
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        text-align: left !important;
    }
    section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] .stButton > button:hover {
        background-color: #D6E8FA !important;
    }
    /* Active conversation */
    section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] .stButton > button[kind="primary"] {
        background-color: #BBDEFB !important;
        color: #0D47A1 !important;
        border: none !important;
        font-weight: 600 !important;
        min-height: 0 !important;
        padding: 6px 10px !important;
        border-radius: 6px !important;
        text-align: left !important;
        justify-content: flex-start !important;
    }
    section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] .stButton > button[kind="primary"]:hover {
        background-color: #B0D4F1 !important;
    }
    /* Delete button */
    section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] [data-testid="stColumn"]:last-child .stButton > button {
        color: #999 !important;
        font-size: 0.8rem !important;
        padding: 6px 4px !important;
        text-align: center !important;
        justify-content: center !important;
    }
    section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] [data-testid="stColumn"]:last-child .stButton > button:hover {
        color: #e53935 !important;
        background-color: rgba(229, 57, 53, 0.08) !important;
    }

    /* Form section styling */
    .form-section {
        background: white;
        border: 1px solid #BBDEFB;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
    }
    .form-section-title {
        color: #1565C0;
        font-weight: 600;
        font-size: 1rem;
        margin-bottom: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────── Session State Init ────────────────────────────

def init_state():
    defaults = {
        "api": APIClient(),
        "logged_in": False,
        "token": None,
        "user": None,
        "current_chatbot": None,
        "current_conversation": None,
        "messages": [],
        "references": [],
        "page": "login",  # login | register | select_chatbot | create_chatbot | chat
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


init_state()


def _get_chat_model_options(api, chatbot: dict) -> list[str]:
    """Build the model dropdown options for the chat page (cached in session)."""
    if "_chat_model_options" not in st.session_state:
        try:
            data = api.list_ollama_models()
            models = [m["name"] for m in data.get("models", [])]
            default = data.get("default", "")
        except Exception:
            models = []
            default = ""

        bot_model = chatbot.get("llm_model")
        default_label = f"기본 ({bot_model or default or 'llama3'})"
        options = [default_label] + [m for m in models if m != bot_model]
        st.session_state["_chat_model_options"] = options
    return st.session_state["_chat_model_options"]


def settings_default_model() -> str:
    """Fetch the default LLM model name from the backend (cached in session)."""
    if "_default_llm_model" not in st.session_state:
        try:
            data = st.session_state.api.list_ollama_models()
            st.session_state["_default_llm_model"] = data.get("default", "llama3")
        except Exception:
            st.session_state["_default_llm_model"] = "llama3"
    return st.session_state["_default_llm_model"]


# ──────────────────────────── Auth Pages ────────────────────────────

def show_login():
    col1, col2, col3 = st.columns([3, 2, 3])
    with col2:
        st.markdown('<div class="main-header"><h2>🏥 병원 매뉴얼 RAG 챗봇</h2></div>', unsafe_allow_html=True)
        st.markdown('<div class="auth-card">', unsafe_allow_html=True)
        st.subheader("로그인")
        with st.form("login_form"):
            username = st.text_input("사용자명")
            password = st.text_input("비밀번호", type="password")
            submitted = st.form_submit_button("로그인", use_container_width=True)
            if submitted:
                try:
                    token = st.session_state.api.login(username, password)
                    st.session_state.token = token
                    st.session_state.logged_in = True
                    st.session_state.user = st.session_state.api.get_me()
                    st.session_state.page = "select_chatbot"
                    st.rerun()
                except Exception as e:
                    st.error("로그인에 실패했습니다. 사용자명과 비밀번호를 확인해주세요.")

        if st.button("회원가입", use_container_width=True):
            st.session_state.page = "register"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)


def show_register():
    col1, col2, col3 = st.columns([3, 2, 3])
    with col2:
        st.markdown('<div class="main-header"><h2>🏥 병원 매뉴얼 RAG 챗봇</h2></div>', unsafe_allow_html=True)
        st.markdown('<div class="auth-card">', unsafe_allow_html=True)
        st.subheader("회원가입")
        with st.form("register_form"):
            username = st.text_input("사용자명")
            email = st.text_input("이메일")
            password = st.text_input("비밀번호", type="password")
            password_confirm = st.text_input("비밀번호 확인", type="password")
            submitted = st.form_submit_button("회원가입", use_container_width=True)
            if submitted:
                if password != password_confirm:
                    st.error("비밀번호가 일치하지 않습니다.")
                elif not username or not email or not password:
                    st.error("모든 필드를 입력해주세요.")
                else:
                    try:
                        st.session_state.api.register(username, email, password)
                        st.success("회원가입이 완료되었습니다! 로그인해주세요.")
                        st.session_state.page = "login"
                        st.rerun()
                    except Exception as e:
                        st.error("회원가입에 실패했습니다. 다른 사용자명/이메일을 사용해주세요.")

        if st.button("로그인으로 돌아가기", use_container_width=True):
            st.session_state.page = "login"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)


# ──────────────────────────── Chatbot Selection Page ────────────────────────────

def show_select_chatbot():
    api: APIClient = st.session_state.api

    # Header bar
    st.markdown('<div class="main-header"><h2>🏥 병원 매뉴얼 RAG 챗봇</h2></div>', unsafe_allow_html=True)

    try:
        chatbots = api.list_chatbots()
    except Exception:
        chatbots = []

    _, center, _ = st.columns([2, 2, 2])
    with center:
        st.markdown('<p class="section-title">서비스를 선택하세요</p>', unsafe_allow_html=True)
        st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

        # All items = existing chatbots + "create new" button
        all_items = chatbots + [{"_create_new": True}]
        num_cols = min(len(all_items), 3)
        cols = st.columns(num_cols)

        for i, item in enumerate(all_items):
            with cols[i % num_cols]:
                if item.get("_create_new"):
                    # "Create new chatbot" card
                    create_label = "➕\n\n**신규 챗봇 만들기**\n\n나만의 챗봇을 만들어보세요"
                    if st.button(create_label, key="create_new_chatbot", use_container_width=True, type="primary"):
                        st.session_state.page = "create_chatbot"
                        st.rerun()
                else:
                    cb = item
                    icon = cb.get("icon") or "🤖"
                    label = f"{icon}\n\n**{cb['name']}**"
                    if cb.get("description"):
                        label += f"\n\n{cb['description']}"
                    if st.button(label, key=f"select_{cb['id']}", use_container_width=True, type="primary"):
                        st.session_state.current_chatbot = cb
                        st.session_state.current_conversation = None
                        st.session_state.messages = []
                        st.session_state.references = []
                        st.session_state.page = "chat"
                        st.rerun()

                    # Delete button for user-created chatbots
                    if cb.get("creator_id"):
                        if st.button("🗑 삭제", key=f"del_chatbot_{cb['id']}", use_container_width=True):
                            try:
                                api.delete_chatbot(cb["id"])
                                st.rerun()
                            except Exception as e:
                                st.error(f"삭제 실패: {e}")

    # Logout button at bottom-right
    _, col_logout = st.columns([5, 1])
    with col_logout:
        if st.button("🚪 로그아웃", key="logout_select", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


# ──────────────────────────── Create Chatbot Page ────────────────────────────

def show_create_chatbot():
    api: APIClient = st.session_state.api

    st.markdown('<div class="main-header"><h2>🏥 신규 챗봇 만들기</h2></div>', unsafe_allow_html=True)

    _, center, _ = st.columns([1, 3, 1])
    with center:
        # Back button
        if st.button("← 서비스 목록으로 돌아가기", key="back_to_select"):
            st.session_state.page = "select_chatbot"
            st.rerun()

        st.markdown("")

        # ── Section 1: Basic Info ──
        st.markdown('<div class="form-section">', unsafe_allow_html=True)
        st.markdown('<p class="form-section-title">📋 기본 정보</p>', unsafe_allow_html=True)

        chatbot_name = st.text_input("챗봇 이름 *", placeholder="예: 인사팀 매뉴얼 봇")
        chatbot_description = st.text_area(
            "챗봇 설명",
            placeholder="예: 인사팀 관련 매뉴얼 기반 질의응답 서비스",
            height=80,
        )

        icon_options = ["🤖", "📚", "🏥", "💼", "📊", "🔬", "💡", "🎯", "📋", "⚙️"]
        chatbot_icon = st.selectbox("아이콘", options=icon_options, index=0)

        # LLM Model selection
        try:
            models_data = api.list_ollama_models()
            available_models = [m["name"] for m in models_data.get("models", [])]
            default_model = models_data.get("default", "")
        except Exception:
            available_models = []
            default_model = ""

        if available_models:
            # Add "서버 기본값" option at the top
            model_options = [f"서버 기본값 ({default_model})"] + available_models
            selected_model_idx = st.selectbox(
                "LLM 모델",
                options=range(len(model_options)),
                format_func=lambda i: model_options[i],
                index=0,
                help="Ollama 서버에 설치된 모델 중 하나를 선택하세요.",
            )
            chatbot_llm_model = None if selected_model_idx == 0 else available_models[selected_model_idx - 1]
        else:
            st.info("Ollama 서버에서 모델 목록을 불러올 수 없습니다. 서버 기본 모델이 사용됩니다.")
            chatbot_llm_model = None

        st.markdown('</div>', unsafe_allow_html=True)

        # ── Section 2: File Upload ──
        st.markdown('<div class="form-section">', unsafe_allow_html=True)
        st.markdown('<p class="form-section-title">📄 자료 업로드</p>', unsafe_allow_html=True)
        st.caption("챗봇이 참고할 PDF 파일을 업로드하세요. 여러 파일을 동시에 업로드할 수 있습니다.")

        uploaded_files = st.file_uploader(
            "PDF 파일 업로드",
            type=["pdf"],
            accept_multiple_files=True,
            label_visibility="collapsed",
        )
        if uploaded_files:
            st.success(f"{len(uploaded_files)}개 파일이 선택되었습니다.")
            for f in uploaded_files:
                st.caption(f"  - {f.name} ({f.size / 1024:.1f} KB)")

        st.markdown('</div>', unsafe_allow_html=True)

        # ── Section 3: Customization (Advanced) ──
        with st.expander("⚙️ 고급 설정 (선택 사항)", expanded=False):
            st.markdown('<div class="form-section">', unsafe_allow_html=True)

            system_prompt = st.text_area(
                "시스템 프롬프트",
                value="",
                placeholder=(
                    "챗봇의 역할과 답변 스타일을 지정합니다.\n"
                    "예: 당신은 인사팀 전문 어시스턴트입니다. "
                    "직원들의 인사 관련 질문에 친절하고 정확하게 답변해주세요."
                ),
                height=120,
                help="비워두면 기본 시스템 프롬프트가 사용됩니다.",
            )

            col_t, col_k = st.columns(2)
            with col_t:
                temperature = st.slider(
                    "Temperature (창의성)",
                    min_value=0.0,
                    max_value=1.0,
                    value=0.7,
                    step=0.1,
                    help="낮을수록 정확하고 일관된 답변, 높을수록 창의적인 답변",
                )
            with col_k:
                top_k = st.slider(
                    "검색 결과 수 (Top-K)",
                    min_value=1,
                    max_value=10,
                    value=5,
                    help="질문에 대해 검색할 관련 문서 수",
                )

            col_d, col_cs = st.columns(2)
            with col_d:
                distance_threshold = st.slider(
                    "유사도 임계값",
                    min_value=0.1,
                    max_value=1.0,
                    value=0.4,
                    step=0.05,
                    help="낮을수록 더 관련성 높은 문서만 사용 (엄격), 높을수록 더 넓은 범위 검색 (관대)",
                )
            with col_cs:
                chunk_size = st.slider(
                    "청크 크기",
                    min_value=200,
                    max_value=1500,
                    value=500,
                    step=50,
                    help="문서를 나누는 단위 크기. 작을수록 세밀, 클수록 넓은 문맥",
                )

            chunk_overlap = st.slider(
                "청크 겹침",
                min_value=0,
                max_value=300,
                value=100,
                step=25,
                help="인접 청크 간 겹치는 글자 수. 문맥 연결을 위해 적절한 값 설정",
            )

            st.markdown('</div>', unsafe_allow_html=True)

        # ── Create Button ──
        st.markdown("")
        if st.button("🚀 챗봇 생성", use_container_width=True, type="primary"):
            if not chatbot_name or not chatbot_name.strip():
                st.error("챗봇 이름을 입력해주세요.")
            elif not uploaded_files:
                st.error("최소 1개의 PDF 파일을 업로드해주세요.")
            else:
                with st.spinner("챗봇을 생성하고 있습니다..."):
                    try:
                        # Step 1: Create the chatbot
                        chatbot_data = {
                            "name": chatbot_name.strip(),
                            "description": chatbot_description.strip() if chatbot_description else None,
                            "icon": chatbot_icon,
                            "llm_model": chatbot_llm_model,
                            "system_prompt": system_prompt.strip() if system_prompt else None,
                            "temperature": temperature,
                            "top_k": top_k,
                            "distance_threshold": distance_threshold,
                            "chunk_size": chunk_size,
                            "chunk_overlap": chunk_overlap,
                        }
                        new_chatbot = api.create_chatbot(chatbot_data)

                        # Step 2: Upload PDF files
                        total_chunks = 0
                        for f in uploaded_files:
                            result = api.upload_pdf(new_chatbot["id"], f)
                            total_chunks += result.get("chunks", 0)

                        st.success(
                            f"챗봇 '{chatbot_name}'이 생성되었습니다! "
                            f"({len(uploaded_files)}개 파일, {total_chunks}개 청크 색인)"
                        )
                        st.balloons()

                        # Navigate to the new chatbot
                        st.session_state.current_chatbot = new_chatbot
                        st.session_state.current_conversation = None
                        st.session_state.messages = []
                        st.session_state.references = []
                        st.session_state.page = "chat"
                        st.rerun()
                    except Exception as e:
                        st.error(f"챗봇 생성에 실패했습니다: {e}")


# ──────────────────────────── Reference Dialog ────────────────────────────

@st.dialog("📄 참고 문서 상세", width="large")
def _show_reference_dialog(index: int, ref: dict):
    source = ref.get("source", "알 수 없음")
    page = ref.get("page")
    full_content = ref.get("full_content", ref.get("content", ""))
    distance = ref.get("distance")

    page_str = f" (p.{page})" if page is not None else ""
    st.markdown(f"### 📄 {source}{page_str}")

    if distance is not None:
        similarity = (1.0 - distance) * 100
        st.markdown(f"**유사도:** {similarity:.1f}%")

    st.divider()
    st.markdown(full_content)

    if st.button("닫기", key=f"close_ref_{index}", use_container_width=True):
        st.session_state[f"_show_ref_{index}"] = False
        st.rerun()


# ──────────────────────────── Chat Page ────────────────────────────

def show_chat():
    api: APIClient = st.session_state.api

    if not st.session_state.current_chatbot:
        st.session_state.page = "select_chatbot"
        st.rerun()
        return

    chatbot = st.session_state.current_chatbot

    # ── Sidebar: Navigation + Conversation History ──
    with st.sidebar:
        st.markdown(f"**👤 {st.session_state.user['username']}**")
        if st.button("🚪 로그아웃", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

        st.divider()

        # Current chatbot info
        icon = chatbot.get("icon") or "🤖"
        st.markdown(f"**{icon} {chatbot['name']}**")
        if st.button("← 서비스 목록", use_container_width=True):
            st.session_state.current_chatbot = None
            st.session_state.current_conversation = None
            st.session_state.messages = []
            st.session_state.references = []
            st.session_state.page = "select_chatbot"
            st.rerun()

        st.divider()

        # Conversation history
        st.markdown("**💬 대화 기록**")
        if st.button("➕ 새 대화", use_container_width=True):
            try:
                conv = api.create_conversation(chatbot["id"])
                st.session_state.current_conversation = conv
                st.session_state.messages = []
                st.session_state.references = []
                st.rerun()
            except Exception:
                st.error("대화 생성 실패")

        try:
            conversations = api.list_conversations(chatbot["id"])
        except Exception:
            conversations = []

        for conv in conversations:
            is_active = (
                st.session_state.current_conversation
                and st.session_state.current_conversation["id"] == conv["id"]
            )
            title = conv["title"] or "새 대화"
            btn_type = "primary" if is_active else "secondary"

            col_title, col_del = st.columns([7, 1])
            with col_title:
                if st.button(
                    title,
                    key=f"conv_{conv['id']}",
                    use_container_width=True,
                    type=btn_type,
                ):
                    try:
                        full_conv = api.get_conversation(conv["id"])
                        st.session_state.current_conversation = full_conv
                        st.session_state.messages = full_conv.get("messages", [])
                        st.session_state.references = []
                        # Load last assistant message references
                        for msg in reversed(full_conv.get("messages", [])):
                            if msg["role"] == "assistant" and msg.get("references"):
                                try:
                                    st.session_state.references = json.loads(
                                        msg["references"]
                                    )
                                except Exception:
                                    pass
                                break
                        st.rerun()
                    except Exception:
                        st.error("대화 불러오기 실패")
            with col_del:
                if st.button("✕", key=f"del_{conv['id']}"):
                    try:
                        api.delete_conversation(conv["id"])
                        if (
                            st.session_state.current_conversation
                            and st.session_state.current_conversation["id"]
                            == conv["id"]
                        ):
                            st.session_state.current_conversation = None
                            st.session_state.messages = []
                            st.session_state.references = []
                        st.rerun()
                    except Exception:
                        st.error("삭제 실패")

    # ── Main Content: Chat + References ──
    model_display = chatbot.get("llm_model") or settings_default_model()
    st.markdown(
        '<div class="main-header">'
        f'<h2>🏥 {chatbot["name"]}</h2>'
        f'<span style="font-size:0.9rem;">{chatbot.get("description") or ""}'
        f' &nbsp;|&nbsp; 모델: {model_display}</span>'
        "</div>",
        unsafe_allow_html=True,
    )

    if not st.session_state.current_conversation:
        st.info("왼쪽 사이드바에서 '새 대화'를 눌러 대화를 시작해주세요.")
        return

    # Two-column layout: Chat (left) + References (right)
    chat_col, ref_col = st.columns([3, 2])

    with chat_col:
        # Chat messages
        chat_container = st.container(height=500)
        with chat_container:
            for msg in st.session_state.messages:
                role = msg["role"]
                content = msg["content"]
                if role == "user":
                    st.markdown(
                        f'<div class="user-message-wrapper"><div class="user-message">{content}</div></div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f'<div class="assistant-message">{content}</div>',
                        unsafe_allow_html=True,
                    )
                    tokens = msg.get("total_tokens", 0)
                    latency = msg.get("latency_ms", 0)
                    if tokens or latency:
                        st.markdown(
                            f'<div class="token-info">토큰: {tokens} | 응답시간: {latency:.0f}ms</div>',
                            unsafe_allow_html=True,
                        )

            # Auto-scroll: scroll to last question, then follow streaming response
            components.html(
                """
                <script>
                    (function() {
                        var sc = null;
                        try {
                            var el = window.frameElement;
                            while (el) {
                                el = el.parentElement;
                                if (el && el.scrollHeight > el.clientHeight + 10) {
                                    var ov = getComputedStyle(el).overflowY;
                                    if (ov !== 'visible' && ov !== 'hidden') { sc = el; break; }
                                }
                            }
                        } catch(e) {}
                        if (!sc) {
                            try {
                                var divs = window.parent.document.querySelectorAll('div');
                                for (var i = 0; i < divs.length; i++) {
                                    var d = divs[i];
                                    if (d.clientHeight >= 300 && d.scrollHeight > d.clientHeight + 10) {
                                        var s = getComputedStyle(d).overflowY;
                                        if (s === 'auto' || s === 'scroll') { sc = d; break; }
                                    }
                                }
                            } catch(e) {}
                        }
                        if (!sc) return;

                        // Find user messages via parent document (more reliable than sc.querySelectorAll)
                        function getUserMsgs() {
                            try { return window.parent.document.querySelectorAll('.user-message-wrapper'); }
                            catch(e) {}
                            try { return sc.querySelectorAll('.user-message-wrapper'); }
                            catch(e) {}
                            return [];
                        }

                        // Scroll container so element is at the top
                        function scrollToLastQ() {
                            var msgs = getUserMsgs();
                            if (msgs.length === 0) { sc.scrollTop = sc.scrollHeight; return 0; }
                            var last = msgs[msgs.length - 1];
                            var mR = last.getBoundingClientRect();
                            var sR = sc.getBoundingClientRect();
                            sc.scrollTop += (mR.top - sR.top);
                            return msgs.length;
                        }

                        // Get initial count before scrolling
                        var numQ = getUserMsgs().length;
                        // Delay initial scroll slightly so Streamlit finishes rendering
                        setTimeout(function() { scrollToLastQ(); }, 100);

                        // Poll: detect new questions + auto-scroll streaming
                        var lastH = sc.scrollHeight;
                        setInterval(function() {
                            var current = getUserMsgs().length;
                            if (current > numQ) {
                                numQ = current;
                                scrollToLastQ();
                                lastH = sc.scrollHeight;
                                return;
                            }
                            var h = sc.scrollHeight;
                            if (h !== lastH) {
                                sc.scrollTop = h;
                                lastH = h;
                            }
                        }, 80);
                    })();
                </script>
                """,
                height=0,
            )

    with ref_col:
        st.markdown("#### 📖 참고 문서 (References)")
        ref_container = st.container(height=500)
        with ref_container:
            if st.session_state.references:
                # Sort references by distance (ascending = most similar first)
                sorted_refs = sorted(
                    st.session_state.references,
                    key=lambda r: r.get("distance", 1.0),
                )
                for i, ref in enumerate(sorted_refs):
                    source = ref.get("source", "알 수 없음")
                    page = ref.get("page", "")
                    content = ref.get("content", "")
                    full_content = ref.get("full_content", content)
                    distance = ref.get("distance")
                    page_str = f" (p.{page})" if page is not None else ""

                    # Compute similarity score (cosine similarity = 1 - cosine distance)
                    if distance is not None:
                        similarity = (1.0 - distance) * 100
                        score_html = f'<span class="ref-score">유사도 {similarity:.1f}%</span>'
                    else:
                        score_html = ""

                    rank_html = f'<span class="ref-rank">#{i + 1}</span>'

                    st.markdown(
                        f'<div class="ref-card">'
                        f'<div class="ref-source">{rank_html}📄 {source}{page_str}{score_html}</div>'
                        f'<div class="ref-content-preview">{content}</div>'
                        f"</div>",
                        unsafe_allow_html=True,
                    )

                    # Button to show full content in a popup dialog
                    if st.button(f"📋 상세 보기", key=f"ref_detail_{i}"):
                        st.session_state[f"_show_ref_{i}"] = True
                        st.rerun()
            else:
                st.caption("질문을 하면 관련 문서 근거가 여기에 표시됩니다.")

        # Show dialog for any active reference popup (outside scroll container)
        if st.session_state.references:
            sorted_refs = sorted(
                st.session_state.references,
                key=lambda r: r.get("distance", 1.0),
            )
            for i, ref in enumerate(sorted_refs):
                if st.session_state.get(f"_show_ref_{i}", False):
                    _show_reference_dialog(i, ref)
                    break

    # ── Model selector + chat input on the same row ──
    _model_options = _get_chat_model_options(api, chatbot)

    model_col, input_col, send_col = st.columns([1.5, 5, 0.6])

    with model_col:
        selected_model_name = st.selectbox(
            "모델 선택",
            options=_model_options,
            index=0,
            key="chat_model_select",
            label_visibility="collapsed",
        )

    with input_col:
        question = st.text_input(
            "질문",
            placeholder="매뉴얼에 대해 질문해주세요...",
            key="chat_question_input",
            label_visibility="collapsed",
        )

    with send_col:
        send_clicked = st.button("전송", use_container_width=True)

    # Resolve the actual model value to send (None means use chatbot/server default)
    if selected_model_name and selected_model_name.startswith("기본"):
        _runtime_model = None
    else:
        _runtime_model = selected_model_name

    if (send_clicked or question) and question:
        st.session_state.messages.append({"role": "user", "content": question})

        stream_meta = {}
        full_text_parts = []

        with chat_container:
            st.markdown(
                f'<div class="user-message-wrapper"><div class="user-message">{question}</div></div>',
                unsafe_allow_html=True,
            )
            placeholder = st.empty()
            placeholder.markdown(
                '<div class="loading-indicator">'
                '<div class="spinner-dots"><span></span><span></span><span></span></div>'
                ' 답변을 준비하고 있습니다...'
                '</div>',
                unsafe_allow_html=True,
            )
            try:
                for chunk in api.chat_stream(
                    st.session_state.current_conversation["id"], question,
                    llm_model=_runtime_model,
                ):
                    if chunk["type"] == "token":
                        full_text_parts.append(chunk["content"])
                        placeholder.markdown(
                            f'<div class="assistant-message">{"".join(full_text_parts)}</div>',
                            unsafe_allow_html=True,
                        )
                    elif chunk["type"] == "meta":
                        stream_meta = {k: v for k, v in chunk.items() if k != "type"}
                    elif chunk["type"] == "error":
                        st.error(f"오류: {chunk.get('message', '알 수 없는 오류')}")
            except Exception as e:
                st.error(f"답변 생성에 실패했습니다: {e}")

        if full_text_parts:
            assistant_msg = {
                "role": "assistant",
                "content": "".join(full_text_parts),
                "prompt_tokens": stream_meta.get("prompt_tokens", 0),
                "completion_tokens": stream_meta.get("completion_tokens", 0),
                "total_tokens": stream_meta.get("total_tokens", 0),
                "latency_ms": stream_meta.get("latency_ms", 0),
            }
            st.session_state.messages.append(assistant_msg)
            st.session_state.references = stream_meta.get("references", [])

        st.rerun()


# ──────────────────────────── Router ────────────────────────────

if st.session_state.page == "login" and not st.session_state.logged_in:
    show_login()
elif st.session_state.page == "register" and not st.session_state.logged_in:
    show_register()
elif st.session_state.page == "select_chatbot":
    show_select_chatbot()
elif st.session_state.page == "create_chatbot":
    show_create_chatbot()
else:
    show_chat()
