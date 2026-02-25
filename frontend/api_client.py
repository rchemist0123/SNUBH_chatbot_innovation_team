import json

import requests

DEFAULT_BASE_URL = "http://localhost:8000"


class APIClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL):
        self.base_url = base_url
        self.token: str | None = None

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    # ── Auth ──

    def register(self, username: str, email: str, password: str) -> dict:
        resp = requests.post(
            f"{self.base_url}/api/auth/register",
            json={"username": username, "email": email, "password": password},
        )
        resp.raise_for_status()
        return resp.json()

    def login(self, username: str, password: str) -> str:
        resp = requests.post(
            f"{self.base_url}/api/auth/login",
            json={"username": username, "password": password},
        )
        resp.raise_for_status()
        data = resp.json()
        self.token = data["access_token"]
        return self.token

    def get_me(self) -> dict:
        resp = requests.get(f"{self.base_url}/api/auth/me", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    # ── Chatbots ──

    def list_chatbots(self) -> list[dict]:
        resp = requests.get(f"{self.base_url}/api/chatbots", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    # ── Conversations ──

    def list_conversations(self, chatbot_id: str | None = None) -> list[dict]:
        params = {}
        if chatbot_id:
            params["chatbot_id"] = chatbot_id
        resp = requests.get(
            f"{self.base_url}/api/conversations",
            headers=self._headers(),
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    def create_conversation(self, chatbot_id: str, title: str | None = None) -> dict:
        resp = requests.post(
            f"{self.base_url}/api/conversations",
            headers=self._headers(),
            json={"chatbot_id": chatbot_id, "title": title},
        )
        resp.raise_for_status()
        return resp.json()

    def get_conversation(self, conversation_id: str) -> dict:
        resp = requests.get(
            f"{self.base_url}/api/conversations/{conversation_id}",
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def delete_conversation(self, conversation_id: str) -> dict:
        resp = requests.delete(
            f"{self.base_url}/api/conversations/{conversation_id}",
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    # ── Chat ──

    def chat(self, conversation_id: str, question: str) -> dict:
        resp = requests.post(
            f"{self.base_url}/api/chat",
            headers=self._headers(),
            json={"conversation_id": conversation_id, "question": question},
            timeout=300,
        )
        resp.raise_for_status()
        return resp.json()

    def chat_stream(self, conversation_id: str, question: str):
        """Stream chat response via SSE. Yields dicts with type 'token', 'meta', or 'done'."""
        with requests.post(
            f"{self.base_url}/api/chat/stream",
            headers=self._headers(),
            json={"conversation_id": conversation_id, "question": question},
            stream=True,
            timeout=300,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    line_str = line.decode("utf-8") if isinstance(line, bytes) else line
                    if line_str.startswith("data: "):
                        data_str = line_str[6:]
                        if data_str == "[DONE]":
                            yield {"type": "done"}
                            break
                        try:
                            yield json.loads(data_str)
                        except json.JSONDecodeError:
                            pass

    # ── Upload ──

    def upload_pdf(self, chatbot_id: str, file) -> dict:
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        resp = requests.post(
            f"{self.base_url}/api/chatbots/{chatbot_id}/upload",
            headers=headers,
            files={"file": (file.name, file, "application/pdf")},
            timeout=600,
        )
        resp.raise_for_status()
        return resp.json()

    def ingest_pdfs(self, chatbot_id: str) -> dict:
        resp = requests.post(
            f"{self.base_url}/api/chatbots/{chatbot_id}/ingest",
            headers=self._headers(),
            timeout=600,
        )
        resp.raise_for_status()
        return resp.json()
