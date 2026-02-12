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
        "page": "login",  # login | register | chat
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
                    st.session_state.page = "chat"
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


# ──────────────────────────── Chat Page ────────────────────────────

def show_chat():
    api: APIClient = st.session_state.api

    # ── Sidebar: Navigation + Conversation History ──
    with st.sidebar:
        st.markdown(f"**👤 {st.session_state.user['username']}**")
        if st.button("🚪 로그아웃", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

        st.divider()

        # Chatbot selector
        st.markdown("**📋 챗봇 선택**")
        try:
            chatbots = api.list_chatbots()
        except Exception:
            chatbots = []

        if not chatbots:
            st.info("등록된 챗봇이 없습니다.")
            with st.expander("➕ 새 챗봇 추가"):
                with st.form("new_chatbot"):
                    cb_name = st.text_input("챗봇 이름")
                    cb_desc = st.text_input("설명")
                    cb_coll = st.text_input("컬렉션 이름 (영문)")
                    if st.form_submit_button("생성"):
                        try:
                            new_cb = api.create_chatbot(cb_name, cb_desc, cb_coll)
                            st.session_state.current_chatbot = new_cb
                            st.rerun()
                        except Exception:
                            st.error("챗봇 생성에 실패했습니다.")
        else:
            chatbot_names = [cb["name"] for cb in chatbots]
            # Determine current index
            current_idx = 0
            if st.session_state.current_chatbot:
                for i, cb in enumerate(chatbots):
                    if cb["id"] == st.session_state.current_chatbot["id"]:
                        current_idx = i
                        break

            selected_name = st.selectbox(
                "챗봇",
                chatbot_names,
                index=current_idx,
                label_visibility="collapsed",
            )
            selected_chatbot = chatbots[chatbot_names.index(selected_name)]

            if (
                not st.session_state.current_chatbot
                or st.session_state.current_chatbot["id"] != selected_chatbot["id"]
            ):
                st.session_state.current_chatbot = selected_chatbot
                st.session_state.current_conversation = None
                st.session_state.messages = []
                st.session_state.references = []
                st.rerun()

            with st.expander("➕ 새 챗봇 추가"):
                with st.form("new_chatbot"):
                    cb_name = st.text_input("챗봇 이름")
                    cb_desc = st.text_input("설명")
                    cb_coll = st.text_input("컬렉션 이름 (영문)")
                    if st.form_submit_button("생성"):
                        try:
                            new_cb = api.create_chatbot(cb_name, cb_desc, cb_coll)
                            st.session_state.current_chatbot = new_cb
                            st.rerun()
                        except Exception:
                            st.error("챗봇 생성에 실패했습니다.")

        st.divider()

        # PDF upload
        if st.session_state.current_chatbot:
            with st.expander("📄 PDF 매뉴얼 업로드"):
                uploaded_file = st.file_uploader("PDF 파일 선택", type=["pdf"], label_visibility="collapsed")
                if uploaded_file and st.button("업로드 및 색인", use_container_width=True):
                    with st.spinner("PDF 업로드 및 색인 중..."):
                        try:
                            result = api.upload_pdf(st.session_state.current_chatbot["id"], uploaded_file)
                            st.success(result["message"])
                        except Exception as e:
                            st.error(f"업로드 실패: {e}")

        st.divider()

        # Conversation history
        st.markdown("**💬 대화 기록**")
        if st.session_state.current_chatbot:
            if st.button("➕ 새 대화", use_container_width=True):
                try:
                    conv = api.create_conversation(st.session_state.current_chatbot["id"])
                    st.session_state.current_conversation = conv
                    st.session_state.messages = []
                    st.session_state.references = []
                    st.rerun()
                except Exception:
                    st.error("대화 생성 실패")

            try:
                conversations = api.list_conversations(st.session_state.current_chatbot["id"])
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
        f'<h2>🏥 {st.session_state.current_chatbot["name"] if st.session_state.current_chatbot else "병원 매뉴얼 RAG 챗봇"}</h2>'
        f'<span style="font-size:0.9rem;">{st.session_state.current_chatbot["description"] or "" if st.session_state.current_chatbot else ""}</span>'
        "</div>",
        unsafe_allow_html=True,
    )

    if not st.session_state.current_chatbot:
        st.info("왼쪽 사이드바에서 챗봇을 선택하거나 새로 추가해주세요.")
        return

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
else:
    show_chat()
