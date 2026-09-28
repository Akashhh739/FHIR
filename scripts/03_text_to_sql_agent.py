"""
Phase 5 — Text-to-SQL agent: LLM writes its own SQL against the DuckDB/Parquet tables.

Chosen over embedding-based RAG because the data is structured, not narrative text.
The LLM is grounded in real query results — it cannot hallucinate numbers.

Prerequisites:
    pip install duckdb openai
    export OPENAI_API_KEY=sk-...
    Run scripts/01_setup_synthea.sh to download the Parquet files first.

Usage:
    python scripts/03_text_to_sql_agent.py
"""

import json
import os
import duckdb
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# ── DuckDB setup ───────────────────────────────────────────────────────────────
con = duckdb.connect()
con.sql("CREATE VIEW patients   AS SELECT * FROM 'gold_patient_features_parquet/*.parquet'")
con.sql("CREATE VIEW conditions AS SELECT * FROM 'silver_conditions_parquet/*.parquet'")
con.sql("CREATE VIEW encounters AS SELECT * FROM 'silver_encounters_parquet/*.parquet'")

SCHEMA = """
patients   (one row per patient): patient_id, age, gender, total_encounters,
           last_encounter_date, active_condition_count, latest_bmi,
           latest_heart_rate, readmitted_30d

conditions (one row per diagnosis): condition_id, patient_id, condition_name,
           condition_code, onset_date, clinical_status

encounters (one row per visit): encounter_id, patient_id, reason,
           start_time, end_time, encounter_class
"""

TOOLS = [{
    "type": "function",
    "function": {
        "name": "run_sql",
        "description": "Run a read-only SELECT query against the patient lakehouse tables.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "A SQL SELECT query."},
            },
            "required": ["query"],
        },
    },
}]


def run_sql(query: str) -> str:
    q = query.strip().lower()
    if not q.startswith("select"):
        return "Error: only SELECT queries are allowed."
    for banned in ["drop", "delete", "update", "insert", "alter", "create", "attach"]:
        if banned in q:
            return f"Error: '{banned}' is not allowed."
    try:
        return con.sql(query).fetchdf().to_string(index=False)
    except Exception as e:
        return f"Query error: {e}"


def ask(question: str) -> None:
    messages = [
        {
            "role": "system",
            "content": (
                f"You are a clinical data analyst with access to a patient lakehouse.\n"
                f"{SCHEMA}\n"
                "Use the run_sql tool to answer questions. "
                "Only state facts the tool actually returned — never invent numbers."
            ),
        },
        {"role": "user", "content": question},
    ]

    response = client.chat.completions.create(model="gpt-4o-mini", messages=messages, tools=TOOLS)
    msg = response.choices[0].message

    while msg.tool_calls:
        messages.append(msg)
        for tool_call in msg.tool_calls:
            args = json.loads(tool_call.function.arguments)
            result = run_sql(args["query"])
            print(f"[SQL] {args['query']}\n")
            messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": result})
        response = client.chat.completions.create(model="gpt-4o-mini", messages=messages, tools=TOOLS)
        msg = response.choices[0].message

    print(msg.content)


if __name__ == "__main__":
    ask("Which conditions are most common among readmitted patients?")
