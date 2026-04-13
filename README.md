# Customer Support Multi-Agent Copilot

This is a small local-only Generative AI multi-agent system built for the assignment. It supports:

- Natural-language questions over structured customer and ticket data stored in SQLite
- Natural-language questions over uploaded policy documents indexed into a local vector database

The implementation uses only open-source/local components and your local Ollama models.

## Tech Stack

- UI: Streamlit
- API: FastAPI
- Multi-agent orchestration: LangGraph
- LLM: Ollama `llama3.2`
- Embeddings: Ollama `nomic-embed-text`
- Structured DB: SQLite
- Vector DB: Local Qdrant
- MCP server: Python MCP server

## Architecture

1. Router agent decides whether the question is about structured data, documents, or both.
2. Structured-data agent generates a safe SQLite `SELECT`, executes it, and summarizes the result.
3. Document agent retrieves relevant policy chunks from the vector store and answers from context.
4. Synthesizer agent merges both answers when a hybrid query is asked.

## Project Structure

```text
backend/
  app/
    main.py
    mcp_server.py
    db.py
    schemas.py
    services/
      agent_graph.py
      structured_agent.py
      document_service.py
  requirements.txt
docs/
  policies/
  demo_script.md
streamlit_app.py
README.md
```

## Setup

```powershell
git clone <your-repo-url>
cd customer-support-multi-agent
python -m venv .venv
.venv\Scripts\activate
pip install -r backend\requirements.txt
```

Start Ollama and pull the models:

```powershell
ollama serve
ollama pull llama3.2
ollama pull nomic-embed-text
```

Start the backend:

```powershell
cd backend
uvicorn app.main:app --reload
```

Start the Streamlit UI in another terminal:

```powershell
cd customer-support-multi-agent
streamlit run streamlit_app.py
```

## Usage

- The app seeds synthetic customers and ticket data automatically.
- Sample policy files are included under `docs/policies/`.
- You can upload `.pdf`, `.txt`, or `.md` policy files from the Streamlit sidebar.
- Ask policy questions like `What is the current refund policy?`
- Ask structured-data questions like `Give me a quick overview of customer Ema's profile and past support ticket details.`
- Ask hybrid questions like `Summarize Raj's open tickets and the refund policy in one response.`

## MCP Server

Run locally with:

```powershell
cd backend
python -m app.mcp_server
```

Available tools:

- `ask_support_copilot`
- `list_seed_customers`
- `rebuild_policy_index`

## MCP Inspector

MCP Inspector is a developer tool for testing and debugging the MCP server. The official npm package is [`@modelcontextprotocol/inspector`](https://www.npmjs.com/package/@modelcontextprotocol/inspector).

This project now includes a helper script so you can launch Inspector more easily on Windows:

```powershell
cd customer-support-multi-agent
npm run mcp:inspector
```

The script is in [start_mcp_inspector.ps1](E:\IN_BUILT_HDD_DATA\customer-support-multi-agent\scripts\start_mcp_inspector.ps1) and prefers `.venv\Scripts\python.exe` when available.

Requirements:

- Node.js and `npm`
- A Python environment with the project dependencies installed

Note:

- This Inspector command runs the local MCP server module `app.mcp_server`.
- If your shell cannot find `python`, create the virtual environment first so the launcher can use `.venv\Scripts\python.exe`.

## API Endpoints

- `GET /health`
- `GET /customers`
- `POST /chat`
- `POST /documents/upload`
- `POST /documents/reindex`
