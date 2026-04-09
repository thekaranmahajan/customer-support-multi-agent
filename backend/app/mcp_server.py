from app.db import get_customer_preview, init_db
from app.services.agent_graph import run_support_graph
from app.services.document_service import index_documents
from mcp.server.fastmcp import FastMCP


mcp = FastMCP("customer-support-copilot")


@mcp.tool()
async def ask_support_copilot(question: str) -> dict:
    """Answer a support question using the local multi-agent system."""
    return await run_support_graph(question, [])


@mcp.tool()
def list_seed_customers() -> list[dict]:
    """List the seeded customers stored in SQLite."""
    return get_customer_preview()


@mcp.tool()
def rebuild_policy_index() -> dict:
    """Re-index local policy documents into the vector store."""
    init_db()
    return {"indexed_documents": index_documents(force_rebuild=True)}


if __name__ == "__main__":
    init_db()
    index_documents(force_rebuild=False)
    mcp.run()
