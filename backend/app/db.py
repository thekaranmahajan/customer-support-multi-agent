import sqlite3
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent / "data"
DB_PATH = DATA_DIR / "customer_support.db"


CUSTOMERS = [
    (
        1,
        "Ema Dawson",
        "ema.dawson@example.com",
        "Premium",
        "Toronto",
        "2024-02-15",
        "Low",
        "Long-term customer who prefers chat support and usually asks about refunds and delivery issues.",
    ),
    (
        2,
        "Raj Patel",
        "raj.patel@example.com",
        "Standard",
        "Vancouver",
        "2025-01-10",
        "Medium",
        "Frequently contacts support for billing clarifications and product replacement timelines.",
    ),
    (
        3,
        "Sofia Martinez",
        "sofia.martinez@example.com",
        "Enterprise",
        "Montreal",
        "2023-11-21",
        "Low",
        "Manages a team account and typically asks about security, access control, and SLA details.",
    ),
]

TICKETS = [
    (
        101,
        1,
        "Refund request for delayed order",
        "Resolved",
        "High",
        "2026-03-11",
        "2026-03-13",
        "Approved a full refund after verifying a carrier delay of more than 10 business days.",
    ),
    (
        102,
        1,
        "Promo code not applying",
        "Closed",
        "Low",
        "2026-02-02",
        "2026-02-03",
        "Support applied the discount manually and confirmed it for the next renewal cycle.",
    ),
    (
        201,
        2,
        "Invoice mismatch on March billing",
        "Open",
        "Medium",
        "2026-04-05",
        "2026-04-08",
        "Finance review is in progress because one add-on was charged twice.",
    ),
    (
        202,
        2,
        "Replacement for damaged device",
        "Pending Customer",
        "Medium",
        "2026-03-20",
        "2026-03-22",
        "Waiting for Raj to upload photos of the damage and confirm the shipping address.",
    ),
    (
        301,
        3,
        "SSO onboarding support",
        "Resolved",
        "High",
        "2026-01-18",
        "2026-01-21",
        "Completed SSO setup and shared admin verification steps with Sofia's IT lead.",
    ),
    (
        302,
        3,
        "Temporary access for contractor",
        "Resolved",
        "Low",
        "2026-03-29",
        "2026-03-29",
        "Recommended a restricted role with an automatic expiry date and audit logging enabled.",
    ),
]


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS customers (
            customer_id INTEGER PRIMARY KEY,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL,
            plan TEXT NOT NULL,
            city TEXT NOT NULL,
            joined_on TEXT NOT NULL,
            churn_risk TEXT NOT NULL,
            profile_summary TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            status TEXT NOT NULL,
            priority TEXT NOT NULL,
            opened_on TEXT NOT NULL,
            last_updated TEXT NOT NULL,
            resolution_notes TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        )
        """
    )

    cursor.execute("SELECT COUNT(*) FROM customers")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            """
            INSERT INTO customers (
                customer_id, full_name, email, plan, city, joined_on, churn_risk, profile_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            CUSTOMERS,
        )

    cursor.execute("SELECT COUNT(*) FROM tickets")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            """
            INSERT INTO tickets (
                ticket_id, customer_id, subject, status, priority, opened_on, last_updated, resolution_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            TICKETS,
        )

    conn.commit()
    conn.close()


def run_select_query(query: str) -> list[dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(query)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_schema_text() -> str:
    return """
Database: customer_support.db

Table: customers
- customer_id INTEGER PRIMARY KEY
- full_name TEXT
- email TEXT
- plan TEXT
- city TEXT
- joined_on TEXT
- churn_risk TEXT
- profile_summary TEXT

Table: tickets
- ticket_id INTEGER PRIMARY KEY
- customer_id INTEGER (FK -> customers.customer_id)
- subject TEXT
- status TEXT
- priority TEXT
- opened_on TEXT
- last_updated TEXT
- resolution_notes TEXT
""".strip()


def get_customer_preview() -> list[dict[str, Any]]:
    return [
        {
            "customer_id": row[0],
            "full_name": row[1],
            "plan": row[2],
            "city": row[3],
        }
        for row in CUSTOMERS
    ]


def get_customer_directory() -> list[dict[str, Any]]:
    return [
        {
            "customer_id": row[0],
            "full_name": row[1],
            "email": row[2],
        }
        for row in CUSTOMERS
    ]
