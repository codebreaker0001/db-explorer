"""
MCP Server — The Main Entry Point
===================================
This is the heart of our project. It creates an MCP server and registers
"tools" that Claude (or any MCP client) can call.

HOW IT WORKS:
1. When you start this file, it creates an MCP server
2. The server advertises its tools to the client (e.g., Claude Desktop)
3. When Claude wants to explore your database, it calls these tools
4. The tools use our ConnectionManager and SchemaInspector to get the data
5. Results are sent back to Claude as formatted text

THE FLOW:
   Claude asks "What tables are in the database?"
       ↓
   Claude calls the `list_tables` tool
       ↓
   Our server receives the request
       ↓
   SchemaInspector queries the database
       ↓
   Results formatted as a nice markdown table
       ↓
   Sent back to Claude, who shows it to you!
"""

import asyncio
import logging
import os
import re
import sys

from dotenv import load_dotenv
from mcp.server import MCPServer
from sqlalchemy import text

from db_explorer.connection import ConnectionManager
from db_explorer.schema import SchemaInspector

# ─── Safety: max rows returned, query timeout ───
MAX_ROWS = int(os.getenv("MAX_ROWS", "500"))
QUERY_TIMEOUT = int(os.getenv("QUERY_TIMEOUT", "30"))

# Words that signal a write operation — we block these
_WRITE_PATTERNS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|REPLACE|RENAME|GRANT|REVOKE)\b",
    re.IGNORECASE,
)

# ─── Setup logging (writes to stderr so it doesn't break MCP messages) ───
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,  # IMPORTANT: MCP uses stdout for messages, so logs go to stderr
)
logger = logging.getLogger(__name__)

# ─── Load environment variables ───
load_dotenv()

# ─── Create our MCP server ───
# This is like registering our server with a name and version
mcp = MCPServer("db-explorer")

# ─── Create our helper objects ───
# These will be initialized when the server connects to a database
connection_manager = ConnectionManager()
schema_inspector: SchemaInspector | None = None


async def ensure_connected():
    """
    Make sure we're connected to the database before doing anything.

    This is called before every tool runs. If we're not connected yet,
    it reads the DATABASE_URL from .env and connects.
    """
    global schema_inspector

    if schema_inspector is not None:
        return  # Already connected

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError(
            "DATABASE_URL not set. Create a .env file with:\n"
            "DATABASE_URL=sqlite:///./sample.db"
        )

    engine = await connection_manager.connect(db_url)
    schema_inspector = SchemaInspector(engine)
    logger.info("Database connection established")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL 1: list_tables
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@mcp.tool()
async def list_tables() -> str:
    """List all tables in the connected database with their row counts.

    Returns a formatted table showing each table name and how many rows it has.
    Use this to get an overview of what data is available in the database.
    """
    await ensure_connected()

    tables = await schema_inspector.list_tables()

    if not tables:
        return "No tables found in the database."

    # Format as a nice markdown table
    lines = []
    lines.append("| # | Table Name | Row Count |")
    lines.append("|---|-----------|-----------|")

    for i, table in enumerate(tables, 1):
        count = table["row_count"] if table["row_count"] >= 0 else "unknown"
        lines.append(f"| {i} | `{table['name']}` | {count} |")

    lines.append(f"\n**Total: {len(tables)} tables**")

    return "\n".join(lines)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL 2: describe_table
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@mcp.tool()
async def describe_table(table_name: str) -> str:
    """Describe the structure of a specific table.

    Shows all columns with their data types, whether they can be null (empty),
    default values, and which columns are primary keys.
    Also shows foreign key relationships (links to other tables).

    Args:
        table_name: The name of the table to describe (e.g., "users", "orders")
    """
    await ensure_connected()

    try:
        # Get table structure
        table_info = await schema_inspector.describe_table(table_name)
    except Exception as e:
        return f"Error: Could not find table '{table_name}'. Run `list_tables` to see available tables.\n\nDetails: {e}"

    # ─── Format the column information ───
    lines = []
    lines.append(f"## Table: `{table_name}`")
    lines.append(f"**Rows:** {table_info['row_count']}")
    lines.append("")

    # Column details table
    lines.append("### Columns")
    lines.append("| Column | Type | Nullable | Default | Primary Key |")
    lines.append("|--------|------|----------|---------|-------------|")

    for col in table_info["columns"]:
        nullable = "YES" if col["nullable"] else "NO"
        default = col["default"] or "-"
        pk = "PK" if col["primary_key"] else ""
        lines.append(f"| `{col['name']}` | {col['type']} | {nullable} | {default} | {pk} |")

    # ─── Show foreign keys (relationships) ───
    try:
        foreign_keys = await schema_inspector.get_foreign_keys(table_name)
        if foreign_keys:
            lines.append("")
            lines.append("### Relationships (Foreign Keys)")
            lines.append("| Column | References |")
            lines.append("|--------|-----------|")
            for fk in foreign_keys:
                lines.append(
                    f"| `{fk['column']}` | `{fk['references_table']}.{fk['references_column']}` |"
                )
    except Exception:
        pass  # Foreign keys are optional info, don't fail if we can't get them

    return "\n".join(lines)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL 3: run_query
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _validate_sql(sql: str) -> str | None:
    """Returns an error message if the SQL is unsafe, None if OK."""
    stripped = sql.strip().rstrip(";")
    if _WRITE_PATTERNS.search(stripped):
        return "Blocked: only SELECT queries are allowed. This server is read-only."
    if stripped.count(";") > 0:
        return "Blocked: multiple statements not allowed (no semicolons mid-query)."
    return None


@mcp.tool()
async def run_query(sql: str, limit: int = 100) -> str:
    """Run a read-only SQL query and return the results as a markdown table.

    Only SELECT queries are allowed. The server blocks INSERT, UPDATE, DELETE,
    DROP, and other write operations for safety.

    Args:
        sql: The SQL SELECT query to run (e.g., "SELECT * FROM customers WHERE city = 'Mumbai'")
        limit: Maximum rows to return (default 100, max 500). Use smaller limits for faster results.
    """
    await ensure_connected()

    # Safety check
    error = _validate_sql(sql)
    if error:
        return error

    limit = min(limit, MAX_ROWS)

    # Add LIMIT if the query doesn't already have one
    sql_lower = sql.strip().lower()
    if "limit" not in sql_lower:
        sql = f"{sql.rstrip().rstrip(';')} LIMIT {limit}"

    try:
        async with connection_manager.engine.connect() as conn:
            result = await asyncio.wait_for(
                conn.execute(text(sql)),
                timeout=QUERY_TIMEOUT,
            )
            rows = result.fetchall()
            columns = list(result.keys())
    except asyncio.TimeoutError:
        return f"Query timed out after {QUERY_TIMEOUT}s. Try a simpler query or add a WHERE clause."
    except Exception as e:
        return f"Query error: {e}"

    if not rows:
        return "Query returned 0 rows."

    # Format as markdown table
    lines = []
    lines.append("| " + " | ".join(columns) + " |")
    lines.append("| " + " | ".join("---" for _ in columns) + " |")
    for row in rows:
        vals = [str(v) if v is not None else "NULL" for v in row]
        lines.append("| " + " | ".join(vals) + " |")

    lines.append(f"\n**{len(rows)} rows returned**")
    if len(rows) == limit:
        lines.append(f"_(capped at {limit} — pass a higher `limit` to see more)_")

    return "\n".join(lines)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL 4: explain_query
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@mcp.tool()
async def explain_query(sql: str) -> str:
    """Show the execution plan for a SQL query.

    This tells you HOW the database will run your query — whether it uses
    indexes, does full table scans, etc. Useful for understanding why a
    query is slow and how to speed it up.

    Args:
        sql: The SQL SELECT query to explain
    """
    await ensure_connected()

    error = _validate_sql(sql)
    if error:
        return error

    explain_sql = f"EXPLAIN QUERY PLAN {sql}" if connection_manager.db_type == "sqlite" else f"EXPLAIN {sql}"

    try:
        async with connection_manager.engine.connect() as conn:
            result = await conn.execute(text(explain_sql))
            rows = result.fetchall()
            columns = list(result.keys())
    except Exception as e:
        return f"Explain error: {e}"

    lines = ["### Query Plan", "```"]
    for row in rows:
        lines.append(" | ".join(str(v) for v in row))
    lines.append("```")
    return "\n".join(lines)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL 5: get_table_stats
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@mcp.tool()
async def get_table_stats(table_name: str) -> str:
    """Get data quality statistics for a table.

    Shows per-column stats: null count, null %, distinct values, and
    min/max for numeric columns. Useful for spotting data quality issues
    like missing values or suspicious ranges.

    Args:
        table_name: The name of the table to analyze
    """
    await ensure_connected()

    try:
        table_info = await schema_inspector.describe_table(table_name)
    except Exception as e:
        return f"Error: Could not find table '{table_name}'.\n\nDetails: {e}"

    col_names = [c["name"] for c in table_info["columns"]]
    total_rows = table_info["row_count"]

    if total_rows == 0:
        return f"Table `{table_name}` is empty."

    # Build one query that computes stats for every column
    # ponytail: single query per column, fine for < 100 columns; batch if perf matters
    stats = []
    async with connection_manager.engine.connect() as conn:
        for col in col_names:
            q = f'''
                SELECT
                    COUNT(*) - COUNT("{col}") AS null_count,
                    COUNT(DISTINCT "{col}") AS distinct_count,
                    MIN("{col}") AS min_val,
                    MAX("{col}") AS max_val
                FROM "{table_name}"
            '''
            try:
                result = await conn.execute(text(q))
                row = result.fetchone()
                null_count = row[0]
                null_pct = round(100 * null_count / total_rows, 1) if total_rows else 0
                stats.append({
                    "column": col,
                    "nulls": null_count,
                    "null_pct": null_pct,
                    "distinct": row[1],
                    "min": row[2],
                    "max": row[3],
                })
            except Exception:
                stats.append({"column": col, "nulls": "?", "null_pct": "?", "distinct": "?", "min": "?", "max": "?"})

    lines = [f"## Stats: `{table_name}` ({total_rows} rows)", ""]
    lines.append("| Column | Nulls | Null % | Distinct | Min | Max |")
    lines.append("|--------|-------|--------|----------|-----|-----|")
    for s in stats:
        lines.append(f"| `{s['column']}` | {s['nulls']} | {s['null_pct']}% | {s['distinct']} | {s['min']} | {s['max']} |")

    return "\n".join(lines)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Start the server
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def main():
    """
    Entry point — starts the MCP server.

    The server communicates over STDIO (standard input/output):
    - It READS requests from stdin (Claude sends tool calls here)
    - It WRITES responses to stdout (results go back to Claude)
    - Logs go to stderr (so they don't interfere with MCP messages)
    """
    logger.info("Starting DB Explorer MCP Server...")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()