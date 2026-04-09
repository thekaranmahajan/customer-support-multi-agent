import os

import requests
import streamlit as st


BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")


st.set_page_config(page_title="Customer Support Copilot", layout="wide")

st.title("Customer Support Multi-Agent Copilot")
st.caption("Local-only Streamlit UI powered by Ollama, SQLite, Qdrant, LangGraph, and FastAPI.")


if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "Ask me about a customer profile, past ticket history, or a policy document. "
                "Try: Give me a quick overview of customer Ema's profile and past support ticket details."
            ),
        }
    ]


with st.sidebar:
    st.subheader("Setup")
    st.code("ollama serve")
    st.code("ollama pull llama3.2")
    st.code("ollama pull nomic-embed-text")

    st.subheader("Sample prompts")
    st.markdown("- What is the current refund policy?")
    st.markdown("- Give me a quick overview of customer Ema's profile and past support ticket details.")
    st.markdown("- Summarize Raj's open tickets and the refund policy in one response.")

    st.subheader("Upload policy files")
    uploaded_files = st.file_uploader(
        "Upload PDF, TXT, or MD policy files",
        type=["pdf", "txt", "md"],
        accept_multiple_files=True,
    )
    if st.button("Upload and Reindex", use_container_width=True):
        if not uploaded_files:
            st.warning("Choose at least one file first.")
        else:
            files = []
            for item in uploaded_files:
                files.append(("files", (item.name, item.getvalue(), item.type or "application/octet-stream")))
            try:
                response = requests.post(f"{BACKEND_URL}/documents/upload", files=files, timeout=120)
                response.raise_for_status()
                payload = response.json()
                st.success(
                    f"Uploaded {len(payload['files'])} file(s). Indexed chunks/documents: {payload['indexed_documents']}"
                )
            except Exception as exc:
                st.error(f"Upload failed: {exc}")

    st.subheader("Seed customers")
    try:
        customer_response = requests.get(f"{BACKEND_URL}/customers", timeout=30)
        customer_response.raise_for_status()
        for customer in customer_response.json():
            st.markdown(f"- **{customer['full_name']}** | {customer['plan']} | {customer['city']}")
    except Exception:
        st.caption("Backend not reachable yet. Start FastAPI first.")


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("meta"):
            st.caption(message["meta"])


prompt = st.chat_input("Ask the copilot")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    history = [
        {"role": message["role"], "content": message["content"]}
        for message in st.session_state.messages[:-1]
    ]

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = requests.post(
                    f"{BACKEND_URL}/chat",
                    json={"message": prompt, "history": history},
                    timeout=120,
                )
                response.raise_for_status()
                payload = response.json()
                st.markdown(payload["answer"])

                meta_parts = [f"route: {payload['route']}"]
                if payload.get("sql_query"):
                    meta_parts.append(f"sql: `{payload['sql_query']}`")
                if payload.get("citations"):
                    meta_parts.append(f"sources: {', '.join(payload['citations'])}")
                meta = " | ".join(meta_parts)
                st.caption(meta)
            except Exception as exc:
                payload = None
                meta = "route: error"
                st.error(f"Request failed: {exc}")

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": payload["answer"] if payload else "The request failed. Check the backend and Ollama.",
            "meta": meta,
        }
    )
