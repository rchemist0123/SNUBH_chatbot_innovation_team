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

    /* Auth form card */
    .auth-card {
        background: white;
        border: 1px solid #BBDEFB;
        border-radius: 16px;
        padding: 2rem 2rem 1.5rem;
        box-shadow: 0 4px 20px rgba(21, 101, 192, 0.08);
        margin-top: 1rem;
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

    # Header bar (no logout button here)
    st.markdown('<div class="main-header"><h2>🏥 병원 매뉴얼 RAG 챗봇</h2></div>', unsafe_allow_html=True)

    try:
        chatbots = api.list_chatbots()
    except Exception:
        chatbots = []

    # Center the content with side padding - half of original width ([1,4,1] → [2,2,2])
    _, center, _ = st.columns([2, 2, 2])
    with center:
        st.markdown('<p class="section-title">서비스를 선택하세요</p>', unsafe_allow_html=True)
        st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

        if not chatbots:
            st.info("현재 이용 가능한 챗봇 서비스가 없습니다. 관리자에게 문의해주세요.")
        else:
            # Display chatbot cards as clickable buttons - no separate 시작하기 button
            num_cols = min(len(chatbots), 3)
            cols = st.columns(num_cols)
            for i, cb in enumerate(chatbots):
                with cols[i % num_cols]:
                    label = f"🤖\n\n**{cb['name']}**"
                    if cb.get("description"):
                        label += f"\n\n{cb['description']}"
                    if st.button(label, key=f"select_{cb['id']}", use_container_width=True, type="primary"):
                        st.session_state.current_chatbot = cb
                        st.session_state.current_conversation = None
                        st.session_state.messages = []
                        st.session_state.references = []
                        st.session_state.page = "chat"
                        st.rerun()

    # Logout button at bottom-right
    _, col_logout = st.columns([5, 1])
    with col_logout:
        if st.button("🚪 로그아웃", key="logout_select", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


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

    # Chat input at top level — Streamlit pins this to the viewport bottom
    question = st.chat_input("매뉴얼에 대해 질문해주세요...")
    if question:
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
                    st.session_state.current_conversation["id"], question
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
else:
    show_chat()
