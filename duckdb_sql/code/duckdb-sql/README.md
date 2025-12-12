# DuckDB SQL Query Skill

A Claude Code skill for generating DuckDB SQL queries across one or more database files.

## What This Skill Does

This skill helps you:
- Generate SQL queries from plain English questions
- Explore and understand DuckDB database structures
- Modify existing SQL queries
- Document your databases with an evolving data dictionary

## Installation

### Option 1: Symlink into a specific project

```bash
cd /path/to/your/project
mkdir -p .claude/skills
ln -s /path/to/duckdb-sql .claude/skills/duckdb-sql
```

### Option 2: Symlink into global skills

```bash
mkdir -p ~/.claude/skills
ln -s /path/to/duckdb-sql ~/.claude/skills/duckdb-sql
```

## Prerequisites

- DuckDB CLI must be installed and available on PATH
- Verify with: `duckdb -version`

## Usage

Once installed, the skill activates automatically when you ask Claude questions about:
- DuckDB queries
- Data analysis on .ddb files
- Exploring database structures

### First Time Setup

When you first use the skill in a project, it will:
1. Ask which .ddb files to document
2. Ask if you have supplementary documentation (code, READMEs, etc.)
3. Generate assets in `duckdb_sql_assets/` directory
4. Detect likely enum columns and ask for your approval to add them

### Example Questions

**Discovery:**
- "What tables are in my DuckDB files?"
- "What columns does the customers table have?"
- "Where is order total stored?"

**Query Generation:**
- "Show me all customers who placed orders in March"
- "Count orders by status"
- "Join customers with orders to see purchase history"

**Modifications:**
- "Add a date filter to this query"
- "Group these results by month"

## Generated Assets

The skill creates and maintains these files in `duckdb_sql_assets/`:

| File | Purpose |
|------|---------|
| `tables_inventory.json` | Manifest of source files and table metadata |
| `schema_<filename>.sql` | Schema dump for each DuckDB file |
| `data_dictionary.md` | Semantic documentation (AI + user enhanced, editable) |

### Asset Workflow

1. **Schema files** are auto-generated from your .ddb files
2. **Discovered facts** are presented for approval during conversations
3. **You approve** facts before they're added to the data dictionary
4. **Data dictionary** grows over time with verified information

## Updating Assets

### Add a new database file
Tell the skill: "Add new_file.ddb to the assets"

### Remove a database file
The skill will detect missing files and ask to clean up

### Refresh after schema changes
The skill detects schema changes and offers to update

## Learning About Your Data

As you use the skill, it learns facts about your data:
- Column purposes
- Relationships between tables
- Type conversion requirements
- Business logic patterns

When the skill discovers new information, it will ask if you want to add it to the data dictionary:
- **For 1-2 discoveries**: Asked inline during the conversation
- **For 3+ discoveries**: Presented as a summary for bulk approval
- **You can always**: Request to see the diff first before approving

Facts you approve are added directly to `data_dictionary.md`, which you can also edit manually at any time.

## Multi-File Queries

When querying across multiple .ddb files, the skill uses DuckDB's ATTACH:

```sql
ATTACH '/path/to/other.ddb' AS other_db;
SELECT * FROM main_table JOIN other_db.other_table ON ...;
```