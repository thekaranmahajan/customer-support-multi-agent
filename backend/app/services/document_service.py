from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams


BASE_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BASE_DIR.parent
DATA_DIR = BASE_DIR / "app" / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
VECTOR_DIR = DATA_DIR / "qdrant_data"
POLICY_DIR = PROJECT_ROOT / "docs" / "policies"
COLLECTION_NAME = "customer_policy_docs"

_llm: ChatOllama | None = None
_embeddings: OllamaEmbeddings | None = None


def get_llm() -> ChatOllama:
    global _llm
    if _llm is None:
        _llm = ChatOllama(model="llama3.2", temperature=0.1)
    return _llm


def get_embeddings() -> OllamaEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = OllamaEmbeddings(model="nomic-embed-text")
    return _embeddings


def extract_pdf_text(file_path: Path) -> str:
    reader = PdfReader(str(file_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages).strip()


def load_source_documents() -> list[Document]:
    docs: list[Document] = []
    for directory in [POLICY_DIR, UPLOAD_DIR]:
        if not directory.exists():
            continue

        for file_path in sorted(directory.glob("*")):
            if file_path.suffix.lower() not in {".pdf", ".txt", ".md"}:
                continue

            if file_path.suffix.lower() == ".pdf":
                text = extract_pdf_text(file_path)
            else:
                text = file_path.read_text(encoding="utf-8").strip()

            if not text:
                continue

            docs.append(
                Document(
                    page_content=text,
                    metadata={
                        "source": file_path.name,
                        "path": str(file_path),
                        "type": file_path.suffix.lower().lstrip("."),
                    },
                )
            )
    return docs


def get_qdrant_client() -> QdrantClient:
    VECTOR_DIR.mkdir(parents=True, exist_ok=True)
    return QdrantClient(path=str(VECTOR_DIR))


def ensure_collection(client: QdrantClient) -> None:
    names = {collection.name for collection in client.get_collections().collections}
    if COLLECTION_NAME in names:
        return

    vector_size = len(get_embeddings().embed_query("refund policy"))
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )


def index_documents(force_rebuild: bool = False) -> int:
    documents = load_source_documents()
    if not documents:
        return 0

    splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=120)
    chunks = splitter.split_documents(documents)

    client = get_qdrant_client()
    names = {collection.name for collection in client.get_collections().collections}

    if force_rebuild and COLLECTION_NAME in names:
        client.delete_collection(COLLECTION_NAME)

    ensure_collection(client)

    vector_store = QdrantVectorStore(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding=get_embeddings(),
    )

    if force_rebuild or COLLECTION_NAME not in names:
        vector_store.add_documents(chunks)
        return len(chunks)

    points_count = client.count(collection_name=COLLECTION_NAME, exact=True).count
    if points_count == 0:
        vector_store.add_documents(chunks)
        return len(chunks)

    return points_count


def get_vector_store() -> QdrantVectorStore:
    client = get_qdrant_client()
    ensure_collection(client)
    return QdrantVectorStore(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding=get_embeddings(),
    )


def save_uploaded_file(filename: str, content: bytes) -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_path = UPLOAD_DIR / filename
    file_path.write_bytes(content)
    return file_path


async def answer_policy_question(question: str, history: list[dict[str, str]]) -> dict[str, Any]:
    try:
        docs = get_vector_store().similarity_search(question, k=4)
    except Exception as exc:
        return {
            "answer": (
                "The policy retrieval service is not ready yet. Make sure Ollama is running and the "
                f"`nomic-embed-text` model is available. Details: {exc}"
            ),
            "citations": [],
        }

    citations = list(dict.fromkeys(doc.metadata.get("source", "unknown") for doc in docs))

    if not docs:
        return {
            "answer": "I could not find any indexed policy content yet. Upload a policy PDF or text file first.",
            "citations": [],
        }

    history_text = "\n".join(
        f"{message['role']}: {message['content']}" for message in history[-6:]
    )
    context = "\n\n".join(
        f"Source: {doc.metadata.get('source', 'unknown')}\n{doc.page_content}" for doc in docs
    )

    prompt = f"""
You are the policy-document specialist in a customer support copilot.
Answer only from the retrieved policy context.
If the context is incomplete, say so clearly.
Prefer short prose unless the question asks for steps.

Conversation history:
{history_text}

Retrieved policy context:
{context}

User question:
{question}
""".strip()

    try:
        response = await get_llm().ainvoke(prompt)
        return {"answer": response.content, "citations": citations}
    except Exception as exc:
        return {
            "answer": (
                "I found relevant policy content, but I could not reach the local Ollama chat model. "
                f"Details: {exc}"
            ),
            "citations": citations,
        }
