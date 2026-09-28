# DB Explorer — MCP Server

An MCP (Model Context Protocol) server that lets Claude explore and query your SQL databases.

## What It Does

Connect this server to Claude Desktop (or any MCP client) and Claude can:
- **List all tables** in your database with row counts
- **Describe table structure** — columns, types, primary keys, foreign keys
- *(Coming soon)* Run read-only SQL queries, explain query plans, and more

## Supported Databases

- SQLite (built-in, no extra setup)
- PostgreSQL (install with `pip install asyncpg`)
- MySQL (install with `pip install aiomysql`)

## Quick Start

### 1. Clone and install

```bash
git clone <your-repo-url>
cd db-explorer
pip install -e "."
```

### 2. Set up your database connection

```bash
cp .env.example .env
# Edit .env and set your DATABASE_URL
```

### 3. Create sample data (optional)

```bash
python seed_database.py
```

This creates a `sample.db` SQLite file with a mini e-commerce database (customers, products, orders).

### 4. Test the server

```bash
python -m db_explorer.server
```

### 5. Connect to Claude Desktop

Edit your Claude Desktop config file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Linux:** `~/.config/Claude/claude_desktop_config.json`
**Windows:** `%AppData%\Claude\claude_desktop_config.json`

Add this:

```json
{
  "mcpServers": {
    "db-explorer": {
      "command": "python",
      "args": ["-m", "db_explorer.server"],
      "cwd": "/absolute/path/to/db-explorer"
    }
  }
}
```

Restart Claude Desktop. You should see "db-explorer" in the connectors menu.

### 6. Try it out!

Ask Claude:
- "What tables are in my database?"
- "Describe the orders table"
- "What's the structure of the customers table?"

## Project Structure

```
db-explorer/
├── .env                  # Your database URL (not committed to git)
├── .env.example          # Template for .env
├── pyproject.toml        # Project config and dependencies
├── seed_database.py      # Creates sample data for testing
├── sample.db             # Sample SQLite database (created by seed script)
├── README.md
└── src/db_explorer/
    ├── __init__.py
    ├── server.py          # MCP server + tool definitions
    ├── connection.py      # Database connection manager
    └── schema.py          # Schema inspection logic
```

## Available Tools

| Tool | Description |
|------|-------------|
| `list_tables` | Lists all tables with row counts |
| `describe_table` | Shows columns, types, keys for a table |
| `run_query` | Runs read-only SQL queries (SELECT only) |
| `explain_query` | Shows the execution plan for a query |
| `get_table_stats` | Per-column null counts, distinct values, min/max |
| `get_indexes` | Shows indexes on a table |
| `get_relationships` | Maps all foreign keys across the whole database |

## License

MIT