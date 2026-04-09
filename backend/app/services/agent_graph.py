from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.services.document_service import answer_policy_question, get_llm
from app.services.structured_agent import answer_customer_question


class SupportGraphState(TypedDict, total=False):
    question: str
    history: list[dict[str, str]]
    route: str
    structured_result: dict[str, Any]
    document_result: dict[str, Any]
    answer: str
    citations: list[str]
    sql_query: str | None


def classify_route(question: str) -> str:
    lowered = question.lower()
    structured_keywords = [
        "customer",
        "profile",
        "ticket",
        "account",
        "plan",
        "billing",
        "ema",
        "raj",
        "sofia",
    ]
    document_keywords = [
        "policy",
        "refund",
        "return",
        "security",
        "privacy",
        "document",
        "upload",
        "kb",
        "knowledge base",
    ]

    has_structured = any(keyword in lowered for keyword in structured_keywords)
    has_document = any(keyword in lowered for keyword in document_keywords)

    if has_structured and has_document:
        return "hybrid"
    if has_structured:
        return "structured"
    if has_document:
        return "document"
    return "general"


async def router_node(state: SupportGraphState) -> dict[str, Any]:
    return {"route": classify_route(state["question"])}


async def structured_node(state: SupportGraphState) -> dict[str, Any]:
    return {"structured_result": await answer_customer_question(state["question"])}


async def document_node(state: SupportGraphState) -> dict[str, Any]:
    return {
        "document_result": await answer_policy_question(
            state["question"],
            state.get("history", []),
        )
    }


async def synthesize_node(state: SupportGraphState) -> dict[str, Any]:
    route = state["route"]
    structured_result = state.get("structured_result", {})
    document_result = state.get("document_result", {})

    if route == "structured":
        return {
            "answer": structured_result.get("answer", "No structured answer available."),
            "citations": [],
            "sql_query": structured_result.get("sql_query"),
        }

    if route == "document":
        return {
            "answer": document_result.get("answer", "No policy answer available."),
            "citations": document_result.get("citations", []),
            "sql_query": None,
        }

    if route == "general":
        prompt = f"""
You are a helpful customer support copilot for an internal support executive.
Answer the question briefly. If the user likely needs customer data or a policy document, suggest that.

Question:
{state["question"]}
""".strip()
        try:
            response = await get_llm().ainvoke(prompt)
            return {"answer": response.content, "citations": [], "sql_query": None}
        except Exception as exc:
            return {
                "answer": (
                    "The local Ollama model is not reachable yet. Start Ollama and try again. "
                    f"Details: {exc}"
                ),
                "citations": [],
                "sql_query": None,
            }

    prompt = f"""
You are the final response agent in a multi-agent customer support copilot.
Combine the structured-data answer and the policy-document answer into one concise response.
Lead with the direct answer, then include any action-oriented note if helpful.

Structured-data answer:
{structured_result.get("answer", "N/A")}

Policy-document answer:
{document_result.get("answer", "N/A")}
""".strip()
    try:
        response = await get_llm().ainvoke(prompt)
        answer = response.content
    except Exception:
        answer = (
            f"Customer view: {structured_result.get('answer', 'N/A')}\n\n"
            f"Policy view: {document_result.get('answer', 'N/A')}"
        )

    return {
        "answer": answer,
        "citations": document_result.get("citations", []),
        "sql_query": structured_result.get("sql_query"),
    }


def route_after_router(state: SupportGraphState) -> str:
    if state["route"] == "structured":
        return "structured"
    if state["route"] == "document":
        return "document"
    if state["route"] == "hybrid":
        return "hybrid"
    return "general"


def route_after_structured(state: SupportGraphState) -> str:
    if state["route"] == "hybrid":
        return "document"
    return "synthesize"


def build_graph():
    graph = StateGraph(SupportGraphState)
    graph.add_node("router", router_node)
    graph.add_node("structured", structured_node)
    graph.add_node("document", document_node)
    graph.add_node("synthesize", synthesize_node)

    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router",
        route_after_router,
        {
            "structured": "structured",
            "document": "document",
            "hybrid": "structured",
            "general": "synthesize",
        },
    )
    graph.add_conditional_edges(
        "structured",
        route_after_structured,
        {
            "document": "document",
            "synthesize": "synthesize",
        },
    )
    graph.add_edge("document", "synthesize")
    graph.add_edge("synthesize", END)
    return graph.compile()


support_graph = build_graph()


async def run_support_graph(question: str, history: list[dict[str, str]]) -> dict[str, Any]:
    result = await support_graph.ainvoke({"question": question, "history": history})
    return {
        "answer": result["answer"],
        "route": result["route"],
        "citations": result.get("citations", []),
        "sql_query": result.get("sql_query"),
        "agent_notes": {
            "structured_agent_used": result["route"] in {"structured", "hybrid"},
            "document_agent_used": result["route"] in {"document", "hybrid"},
        },
    }
