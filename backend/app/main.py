from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.db import get_customer_preview, init_db
from app.schemas import ChatRequest, ChatResponse, CustomerPreview, UploadResponse
from app.services.agent_graph import run_support_graph
from app.services.document_service import index_documents, save_uploaded_file


app = FastAPI(title="Customer Support Multi-Agent Copilot", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event() -> None:
    init_db()
    try:
        index_documents(force_rebuild=False)
    except Exception as exc:
        print(f"[startup] document indexing skipped: {exc}")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/customers", response_model=list[CustomerPreview])
async def customers() -> list[dict]:
    return get_customer_preview()


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    history = [{"role": item.role, "content": item.content} for item in request.history]
    try:
        result = await run_support_graph(request.message.strip(), history)
        return ChatResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/documents/upload", response_model=UploadResponse)
async def upload_documents(files: list[UploadFile] = File(...)) -> UploadResponse:
    saved_files: list[str] = []
    for file in files:
        if not file.filename:
            continue
        content = await file.read()
        save_uploaded_file(file.filename, content)
        saved_files.append(file.filename)

    indexed_documents = index_documents(force_rebuild=True)
    return UploadResponse(files=saved_files, indexed_documents=indexed_documents)


@app.post("/documents/reindex")
async def reindex_documents() -> dict:
    return {"indexed_documents": index_documents(force_rebuild=True)}
