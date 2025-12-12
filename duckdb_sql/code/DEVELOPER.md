# DuckDB SQL Skill - Developer Documentation

This document provides complete context for iterating on and improving the duckdb-sql skill.

---

## Skill Architecture

### Core Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Asset location | Working directory (`duckdb_sql_assets/`) | Skill is reusable; project-specific data stays with project |
| Schema files | One per database file | Avoids confusion about which tables come from where |
| Data dictionary | Single unified file with rich structure | Cross-file relationships documented in one place |
| Enum detection | Auto-detect via sampling with hardcoded thresholds | Sensible defaults work for 95% of use cases; special cases handled conversationally |
| Statistics | Schema-only (no row counts) | Prevents stale data; schema changes less frequently |
| Fact collection | Via inline approval | Inferred facts presented during conversation for immediate approval |
| Bulk approval | Supported | User can approve multiple discoveries at once via summary presentation |
| Query execution | Display-only by default | Users review/copy queries; execution only on explicit request |

### Key Principles

1. **Never hallucinate columns** - Always validate against schema files before generating SQL
2. **User approval for all facts** - All AI-inferred facts require user approval via inline questions before dictionary entry
3. **Two-step query workflow** - Present plan for approval before writing SQL
4. **Conversational setup** - Guide user through initial configuration
5. **Display-only by default** - Generate and display queries; only execute when user explicitly requests

---

## File Structure

### Skill Directory (Reusable)
```
duckdb-sql/
├── SKILL.md    # Core instructions, frontmatter, workflows
└── README.md   # User-facing installation and usage docs
```

### Asset Directory (Per-Project)
```
duckdb_sql_assets/
├── tables_inventory.json    # Manifest: source files, tables, columns
├── schema_<filename>.sql    # One schema file per .ddb file
└── data_dictionary.md       # Semantic documentation (editable by user)
```

---

## Workflows

### 1. Initial Setup (First Use)

When `duckdb_sql_assets/` doesn't exist:

1. Ask: "Which .ddb files should I document?"
2. Ask: "Do you have any code or documentation that explains this data?"
3. Generate assets:
   - `tables_inventory.json` via duckdb CLI
   - `schema_<filename>.sql` for each database
   - Draft `data_dictionary.md` with rich structure (domains, table entries, relationships)
4. Run enum detection with hardcoded thresholds (max_cardinality=20, max_ratio=0.05, sample_size=10000)
5. Present findings:
   - If 1-2 enums: Ask inline per enum
   - If 3+ enums: Present bulk summary for approval
6. If approved, update `data_dictionary.md` directly with enum documentation

### 2. Query Generation

1. User asks for a query
2. Read `tables_inventory.json` and `data_dictionary.md`
3. **Step 1:** Present query plan (tables, joins, filters)
4. User approves plan
5. **Step 2:** Validate against schema files, generate SQL
6. If something new is learned, ask user if it should be added to the data dictionary

### 3. Schema Update Detection

On skill invocation, check for changes:

- **Files removed:** Prompt to clean up assets
- **Files added:** User requests "add new_file.ddb", skill generates assets
- **Schema changes:** Detect new/removed columns, offer to update

Update actions:
- Removed files: Delete schema file, update inventory and dictionary
- Added files: Generate schema, update inventory, add dictionary stubs, run enum detection and present findings
- Schema changes: Regenerate schema file, update inventory, run enum detection on new VARCHAR/TEXT columns

### 4. Inline Fact Discovery

When the skill discovers new information about the data:

1. **For 1-2 facts:** Ask inline "I discovered [fact]. Should I add this to the data dictionary?"
2. **For 3+ facts:** Present summary in one message and ask for bulk decision
3. **User options:**
   - "Yes" → Add to data_dictionary.md immediately
   - "Show diff first" → Describe changes, then user decides
   - "Add only X, Y" → Add subset
   - "No" → Skip
4. **After approval:** Use Edit tool to update data_dictionary.md, report what was changed

### 5. Enum Detection

During setup and on-demand, the skill scans for likely enum columns using hardcoded thresholds:

**Hardcoded Thresholds:**
- `max_cardinality`: 20 (max distinct values)
- `max_ratio`: 0.05 (max 5% unique values in sample)
- `sample_size`: 10000 (rows to sample per table)
- `name_patterns`: ["status", "type", "state", "category", "level", "role", "kind"] (prioritized columns)

**Detection Heuristics:**
A column is flagged as likely enum if ALL are true:
1. Type is VARCHAR or TEXT
2. `distinct_count <= 20`
3. `distinct_count / sampled_rows < 0.05`

**Re-running:** User can request different thresholds conversationally (e.g., "detect enums with up to 50 values").

---

## Asset File Formats

### tables_inventory.json

```json
{
  "generated_at": "2025-12-11T17:30:00Z",
  "duckdb_version": "v1.3.2",
  "sources": [
    {
      "file_path": "/absolute/path/to/file.ddb",
      "file_name": "file.ddb",
      "tables": ["table1", "table2"]
    }
  ],
  "tables": {
    "table1": {
      "source_file": "file.ddb",
      "columns": [
        {"name": "col1", "type": "VARCHAR"},
        {"name": "col2", "type": "INTEGER"}
      ]
    }
  }
}
```

### schema_<filename>.sql

```sql
-- Schema for <filename>.ddb
-- Generated: YYYY-MM-DD
-- DuckDB version: vX.X.X

CREATE TABLE tablename(
  column1 TYPE,
  column2 TYPE
);
```

### data_dictionary.md

Rich structure format:

```markdown
# Data Dictionary

**Version:** 1.0
**Generated:** YYYY-MM-DD
**Source Files:** file1.ddb, file2.ddb

## Table of Contents

### By Domain
- **sales**: Order processing and transactions
  - [customers](#customers)
  - [orders](#orders)
- **inventory**: Product and stock management
  - [products](#products)

### All Tables
- [customers](#customers)
- [orders](#orders)
- [products](#products)

---

## Domains Overview

### Sales
Order processing and transactions.

**Tables:** `customers`, `orders`, `order_items`

---

## Tables

### tablename

**Purpose:** What this table stores and why it exists.

**Source file:** sales.ddb

**Also known as:** synonyms users might use (e.g., "transactions", "purchases")

**Relationships:**
- Belongs to customer (customers.customer_id)
- Has many order_items (order_items.order_id)

**Important Query Patterns:**
- Active records: `WHERE status != 'cancelled'`
- Recent records: `WHERE created_at >= current_date - INTERVAL '30 days'`

**Fields:**

| Field | Type | Purpose | Notes |
|-------|------|---------|-------|
| id | INTEGER | Primary key | Auto-increment |
| customer_id | INTEGER | Foreign key to customers | Required |
| status | VARCHAR | Record status | Enum: see below |

**Enum Values:**

*status:*
- `pending` - Awaiting processing
- `completed` - Successfully finished
- `cancelled` - User cancelled
```

---

## DuckDB CLI Commands

### Extract schema
```bash
duckdb file.ddb -c ".schema" > schema_file.sql
```

### List tables
```bash
duckdb file.ddb -c "SELECT table_name FROM information_schema.tables WHERE table_schema='main';"
```

### Describe table
```bash
duckdb file.ddb -c "DESCRIBE tablename;"
```

### Get column info
```bash
duckdb file.ddb -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name='tablename';"
```

### Get VARCHAR columns (for enum detection)
```bash
duckdb file.ddb -c "SELECT column_name, table_name FROM information_schema.columns WHERE table_schema='main' AND data_type IN ('VARCHAR', 'TEXT');"
```

### Check column cardinality (for enum detection)
```bash
duckdb file.ddb -c "WITH sampled AS (SELECT status FROM orders LIMIT 10000) SELECT COUNT(DISTINCT status) as distinct_count, COUNT(*) as sample_size FROM sampled;"
```

### Sample distinct values (for enum detection)
```bash
duckdb file.ddb -c "SELECT DISTINCT status FROM orders WHERE status IS NOT NULL LIMIT 25;"
```

### Check version
```bash
duckdb -version
```

---

## DuckDB Syntax Notes

Key differences from PostgreSQL:

| Feature | DuckDB | PostgreSQL |
|---------|--------|------------|
| String concat | `\|\|` | `\|\|` or `CONCAT()` |
| Case-insensitive LIKE | `ILIKE` | `ILIKE` |
| Date truncate | `date_trunc('month', col)` | Same |
| Type cast | `col::TYPE` or `CAST()` | Same |
| Multi-file | `ATTACH 'file.ddb' AS alias` | N/A |

### Multi-File Query Pattern
```sql
ATTACH '/path/to/other.ddb' AS other_db;
SELECT * FROM main_table m
JOIN other_db.other_table o ON m.id = o.id;
```

---

## Example Test Setup

For development and testing, create sample DuckDB files:

**sales.ddb** - Customer and order data:
```sql
-- Create with: duckdb sales.ddb
CREATE TABLE customers(
  customer_id INTEGER PRIMARY KEY,
  name VARCHAR,
  email VARCHAR,
  created_at DATE
);

CREATE TABLE orders(
  order_id INTEGER PRIMARY KEY,
  customer_id INTEGER,
  order_date DATE,
  total_amount DECIMAL(10,2),
  status VARCHAR
);

-- Insert sample data
INSERT INTO customers VALUES
  (1, 'Alice Smith', 'alice@example.com', '2024-01-15'),
  (2, 'Bob Jones', 'bob@example.com', '2024-02-20');

INSERT INTO orders VALUES
  (101, 1, '2024-03-01', 99.99, 'completed'),
  (102, 1, '2024-03-15', 149.50, 'completed'),
  (103, 2, '2024-03-20', 75.00, 'pending');
```

**inventory.ddb** - Product inventory:
```sql
-- Create with: duckdb inventory.ddb
CREATE TABLE products(
  product_id INTEGER PRIMARY KEY,
  name VARCHAR,
  category VARCHAR,
  price DECIMAL(10,2)
);

CREATE TABLE stock(
  product_id INTEGER,
  warehouse VARCHAR,
  quantity INTEGER,
  last_updated TIMESTAMP
);
```

**Cross-file join example:** `orders.customer_id` joins to `customers.customer_id` within same file; cross-file joins require ATTACH.

---

## Future Improvements

Ideas for iteration:

1. **Auto-detect schema changes** - Run schema extraction on invocation and diff against stored
2. **Richer observation types** - Categorize observations (relationship, enum values, business logic)
3. **Query templates** - Store successful queries as reusable patterns
4. **Export to other formats** - Generate ERD diagrams, export to JSON schema
5. **Validation rules** - Add constraints/validation info to dictionary
6. **Version history** - Track dictionary changes over time
7. **Cross-project sharing** - Share dictionary fragments between related projects

---

## Development Setup

To test the skill during development:

```bash
# From this project directory, symlink the skill
mkdir -p .claude/skills
ln -s "$(pwd)/duckdb-sql" .claude/skills/duckdb-sql

# Or install globally
ln -s "$(pwd)/duckdb-sql" ~/.claude/skills/duckdb-sql
```

To create test databases from the example setup above:
```bash
# Create sales.ddb
duckdb sales.ddb < sales_setup.sql

# Create inventory.ddb
duckdb inventory.ddb < inventory_setup.sql
```

Then start a Claude Code session and ask a DuckDB question to trigger the skill.

---

## Skill Files

Current implementation:

| File | Location | Purpose |
|------|----------|---------|
| SKILL.md | `duckdb-sql/SKILL.md` | Core instructions and workflows |
| README.md | `duckdb-sql/README.md` | User installation and usage |
| DEVELOPER.md | This file | Context for future iteration |

Generated assets (created per-project in `duckdb_sql_assets/`):

| File | Purpose |
|------|---------|
| tables_inventory.json | Manifest of source files and tables |
| schema_*.sql | One schema file per database |
| data_dictionary.md | Semantic documentation (editable by user) |
