import json

import streamlit as st

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
    .user-message {
        background-color: #1565C0;
        color: white;
        padding: 12px 18px;
        border-radius: 18px 18px 4px 18px;
        margin: 8px 0;
        max-width: 80%;
        margin-left: auto;
        text-align: right;
    }
    .assistant-message {
        background-color: #E3F2FD;
        color: #0D47A1;
        padding: 12px 18px;
        border-radius: 18px 18px 18px 4px;
        margin: 8px 0;
        max-width: 80%;
    }

    /* Reference card */
    .ref-card {
        background-color: #E8EAF6;
        border-left: 4px solid #1565C0;
        padding: 10px 14px;
        border-radius: 6px;
        margin: 6px 0;
        font-size: 0.85rem;
    }
    .ref-card .ref-source {
        font-weight: bold;
        color: #1565C0;
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

    /* Chatbot service card */
    .chatbot-card {
        background: white;
        border: 2px solid #90CAF9;
        border-radius: 12px;
        padding: 16px;
        text-align: center;
        cursor: pointer;
        transition: all 0.2s;
    }
    .chatbot-card:hover {
        border-color: #1565C0;
        box-shadow: 0 2px 8px rgba(21, 101, 192, 0.15);
    }
    .chatbot-card.active {
        border-color: #1565C0;
        background: #E3F2FD;
    }
    .chatbot-card h4 {
        margin: 8px 0 4px;
        color: #0D47A1;
    }
    .chatbot-card p {
        margin: 0;
        font-size: 0.85rem;
        color: #546E7A;
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
        "page": "login",  # login | register | select_chatbot | chat
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


init_state()


# ──────────────────────────── Auth Pages ────────────────────────────

def show_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="main-header"><h2>🏥 병원 매뉴얼 RAG 챗봇</h2></div>', unsafe_allow_html=True)
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


def show_register():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="main-header"><h2>🏥 병원 매뉴얼 RAG 챗봇</h2></div>', unsafe_allow_html=True)
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


# ──────────────────────────── Chatbot Selection Page ────────────────────────────

def show_select_chatbot():
    api: APIClient = st.session_state.api

    st.markdown('<div class="main-header"><h2>🏥 병원 매뉴얼 RAG 챗봇</h2></div>', unsafe_allow_html=True)

    col_title, col_logout = st.columns([5, 1])
    with col_title:
        st.subheader("서비스를 선택하세요")
    with col_logout:
        if st.button("🚪 로그아웃"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    try:
        chatbots = api.list_chatbots()
    except Exception:
        chatbots = []

    if not chatbots:
        st.info("현재 이용 가능한 챗봇 서비스가 없습니다. 관리자에게 문의해주세요.")
        return

    # Display chatbot cards in a grid
    cols = st.columns(min(len(chatbots), 3))
    for i, cb in enumerate(chatbots):
        with cols[i % 3]:
            st.markdown(
                f'<div class="chatbot-card">'
                f'<div style="font-size:2rem;">🤖</div>'
                f'<h4>{cb["name"]}</h4>'
                f'<p>{cb.get("description") or ""}</p>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if st.button("시작하기", key=f"select_{cb['id']}", use_container_width=True):
                st.session_state.current_chatbot = cb
                st.session_state.current_conversation = None
                st.session_state.messages = []
                st.session_state.references = []
                st.session_state.page = "chat"
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
        st.markdown(f"**🤖 {chatbot['name']}**")
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
            col_btn, col_del = st.columns([5, 1])
            with col_btn:
                is_active = (
                    st.session_state.current_conversation
                    and st.session_state.current_conversation["id"] == conv["id"]
                )
                label = f"{'▶ ' if is_active else ''}{conv['title'] or '새 대화'}"
                if st.button(label, key=f"conv_{conv['id']}", use_container_width=True):
                    try:
                        full_conv = api.get_conversation(conv["id"])
                        st.session_state.current_conversation = full_conv
                        st.session_state.messages = full_conv.get("messages", [])
                        st.session_state.references = []
                        # Load last assistant message references
                        for msg in reversed(full_conv.get("messages", [])):
                            if msg["role"] == "assistant" and msg.get("references"):
                                try:
                                    st.session_state.references = json.loads(msg["references"])
                                except Exception:
                                    pass
                                break
                        st.rerun()
                    except Exception:
                        st.error("대화 불러오기 실패")
            with col_del:
                if st.button("🗑", key=f"del_{conv['id']}"):
                    try:
                        api.delete_conversation(conv["id"])
                        if (
                            st.session_state.current_conversation
                            and st.session_state.current_conversation["id"] == conv["id"]
                        ):
                            st.session_state.current_conversation = None
                            st.session_state.messages = []
                            st.session_state.references = []
                        st.rerun()
                    except Exception:
                        st.error("삭제 실패")

    # ── Main Content: Chat + References ──
    st.markdown(
        '<div class="main-header">'
        f'<h2>🏥 {chatbot["name"]}</h2>'
        f'<span style="font-size:0.9rem;">{chatbot.get("description") or ""}</span>'
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
                        f'<div class="user-message">{content}</div>',
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

        # Chat input
        question = st.chat_input("매뉴얼에 대해 질문해주세요...")
        if question:
            # Add user message to display
            st.session_state.messages.append({"role": "user", "content": question})

            with st.spinner("답변 생성 중..."):
                try:
                    result = api.chat(st.session_state.current_conversation["id"], question)
                    assistant_msg = {
                        "role": "assistant",
                        "content": result["answer"],
                        "prompt_tokens": result["prompt_tokens"],
                        "completion_tokens": result["completion_tokens"],
                        "total_tokens": result["total_tokens"],
                        "latency_ms": result["latency_ms"],
                    }
                    st.session_state.messages.append(assistant_msg)
                    st.session_state.references = result.get("references", [])
                except Exception as e:
                    st.error(f"답변 생성에 실패했습니다: {e}")

            st.rerun()

    with ref_col:
        st.markdown("#### 📖 참고 문서 (References)")
        if st.session_state.references:
            for i, ref in enumerate(st.session_state.references):
                source = ref.get("source", "알 수 없음")
                page = ref.get("page", "")
                content = ref.get("content", "")
                page_str = f" (p.{page})" if page is not None else ""
                st.markdown(
                    f'<div class="ref-card">'
                    f'<div class="ref-source">📄 {source}{page_str}</div>'
                    f"<div>{content}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("질문을 하면 관련 문서 근거가 여기에 표시됩니다.")


# ──────────────────────────── Router ────────────────────────────

if st.session_state.page == "login" and not st.session_state.logged_in:
    show_login()
elif st.session_state.page == "register" and not st.session_state.logged_in:
    show_register()
elif st.session_state.page == "select_chatbot":
    show_select_chatbot()
else:
    show_chat()
