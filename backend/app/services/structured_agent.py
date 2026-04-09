import json
import re
from typing import Any

from app.db import get_customer_directory, get_schema_text, run_select_query
from app.services.document_service import get_llm


SQL_FENCE_RE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
NAME_TOKEN_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b")


def normalize_sql(raw_text: str) -> str:
    match = SQL_FENCE_RE.search(raw_text)
    query = match.group(1) if match else raw_text
    return query.strip().strip(";")


def validate_sql(query: str) -> None:
    lowered = query.lower().strip()
    if not lowered.startswith("select"):
        raise ValueError("Only SELECT queries are allowed.")
    if ";" in query or "--" in query:
        raise ValueError("Only a single plain SELECT statement is allowed.")
    blocked = ["insert ", "update ", "delete ", "drop ", "alter ", "pragma ", "attach "]
    if any(token in lowered for token in blocked):
        raise ValueError("Unsafe SQL was generated.")


def resolve_customer_hint(question: str) -> dict[str, Any] | None:
    lowered_question = question.lower()
    candidates = get_customer_directory()

    for customer in candidates:
        full_name = customer["full_name"]
        full_name_lower = full_name.lower()
        first_name_lower = full_name_lower.split()[0]
        email_lower = customer["email"].lower()

        if full_name_lower in lowered_question:
            return customer
        if re.search(rf"\b{re.escape(first_name_lower)}\b", lowered_question):
            return customer
        if email_lower in lowered_question:
            return customer

    capitalized_tokens = NAME_TOKEN_RE.findall(question)
    for token in capitalized_tokens:
        token_lower = token.lower()
        for customer in candidates:
            if token_lower in customer["full_name"].lower():
                return customer

    return None


def build_direct_customer_sql(question: str, customer: dict[str, Any]) -> str | None:
    lowered = question.lower()
    customer_id = customer["customer_id"]

    if "open ticket" in lowered or "open tickets" in lowered:
        return (
            "SELECT c.full_name, c.plan, t.subject, t.status, t.priority, t.opened_on, "
            "t.last_updated, t.resolution_notes "
            "FROM customers c "
            "JOIN tickets t ON c.customer_id = t.customer_id "
            f"WHERE c.customer_id = {customer_id} AND LOWER(t.status) = 'open' "
            "ORDER BY t.opened_on DESC"
        )

    if "profile" in lowered or "overview" in lowered or "past support ticket" in lowered or "ticket details" in lowered:
        return (
            "SELECT c.full_name, c.email, c.plan, c.city, c.joined_on, c.churn_risk, c.profile_summary, "
            "t.subject, t.status, t.priority, t.opened_on, t.last_updated, t.resolution_notes "
            "FROM customers c "
            "LEFT JOIN tickets t ON c.customer_id = t.customer_id "
            f"WHERE c.customer_id = {customer_id} "
            "ORDER BY t.opened_on DESC"
        )

    return None


async def generate_sql(
    question: str,
    previous_error: str | None = None,
    customer_hint: dict[str, Any] | None = None,
) -> str:
    repair_text = f"\nPrevious SQLite error: {previous_error}\nFix the query.\n" if previous_error else ""
    customer_text = ""
    if customer_hint:
        customer_text = (
            "\nResolved customer reference:\n"
            f"- customer_id: {customer_hint['customer_id']}\n"
            f"- full_name: {customer_hint['full_name']}\n"
            f"- email: {customer_hint['email']}\n"
            "Prefer filtering by customer_id when this customer is clearly the subject.\n"
        )
    prompt = f"""
You are a SQLite expert writing queries for a customer support assistant.
Return exactly one SQLite SELECT statement and nothing else.
Always qualify joins explicitly.
Use LIMIT 10 unless the question clearly asks for a single customer or single ticket.
If looking up a person by name, use LOWER(full_name) LIKE '%name fragment%'.

Schema:
{get_schema_text()}
{customer_text}
{repair_text}
Question:
{question}
""".strip()
    response = await get_llm().ainvoke(prompt)
    return normalize_sql(response.content)


async def summarize_rows(question: str, query: str, rows: list[dict[str, Any]]) -> str:
    prompt = f"""
You are the structured-data specialist in a customer support copilot.
Summarize the SQL result for the support executive in clear prose.
Keep it concise but include the most important customer facts, ticket statuses, and next actions.

Question:
{question}

SQL used:
{query}

Rows:
{json.dumps(rows, indent=2)}
""".strip()
    response = await get_llm().ainvoke(prompt)
    return response.content


async def answer_customer_question(question: str) -> dict[str, Any]:
    customer_hint = resolve_customer_hint(question)
    direct_sql = build_direct_customer_sql(question, customer_hint) if customer_hint else None

    if direct_sql:
        try:
            rows = run_select_query(direct_sql)
            if not rows:
                return {
                    "answer": f"I found {customer_hint['full_name']} but there are no matching ticket records for that specific request.",
                    "sql_query": direct_sql,
                    "rows": [],
                }
            answer = await summarize_rows(question, direct_sql, rows)
            return {"answer": answer, "sql_query": direct_sql, "rows": rows}
        except Exception as exc:
            return {
                "answer": f"I found the customer match but could not complete the direct query. Details: {exc}",
                "sql_query": direct_sql,
                "rows": [],
            }

    sql_query = ""
    last_error: str | None = None

    for _ in range(2):
        try:
            sql_query = await generate_sql(
                question,
                previous_error=last_error,
                customer_hint=customer_hint,
            )
        except Exception as exc:
            return {
                "answer": (
                    "The structured-data agent could not reach the local Ollama model. "
                    f"Make sure `llama3.2` is available. Details: {exc}"
                ),
                "sql_query": None,
                "rows": [],
            }

        try:
            validate_sql(sql_query)
            rows = run_select_query(sql_query)
            if not rows:
                return {
                    "answer": "I checked the customer database but did not find matching records for that request.",
                    "sql_query": sql_query,
                    "rows": [],
                }
            try:
                answer = await summarize_rows(question, sql_query, rows)
            except Exception as exc:
                return {
                    "answer": (
                        "I ran the SQL query successfully, but I could not summarize the results because the "
                        f"local Ollama model is unavailable. Raw row count: {len(rows)}. Details: {exc}"
                    ),
                    "sql_query": sql_query,
                    "rows": rows,
                }
            return {"answer": answer, "sql_query": sql_query, "rows": rows}
        except Exception as exc:
            last_error = str(exc)

    return {
        "answer": f"I could not complete the customer-data query safely. Last error: {last_error}",
        "sql_query": sql_query,
        "rows": [],
    }
