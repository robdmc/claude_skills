# DuckDB SQL Skill - Developer Documentation

This document provides complete context for iterating on and improving the duckdb-sql skill.

---

## Skill Architecture

### Core Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Asset location | Working directory (`duckdb_sql_assets/`) | Skill is reusable; project-specific data stays with project |
| Supported file types | .ddb, .csv, .parquet + glob patterns | Leverage DuckDB's native file reading capabilities |
| Schema files | One per source file | Avoids confusion about which tables come from where |
| Data dictionary | Single unified file with rich structure | Cross-file relationships documented in one place |
| Enum detection | Auto-detect via sampling with hardcoded thresholds | Sensible defaults work for 95% of use cases; special cases handled conversationally |
| Statistics | Schema-only (no row counts) | Prevents stale data; schema changes less frequently |
| Fact collection | Via inline approval | Inferred facts presented during conversation for immediate approval |
| Bulk approval | Supported | User can approve multiple discoveries at once via summary presentation |
| Query execution | Display-only by default | Users review/copy queries; execution only on explicit request |
| CSV auto-detection | Trust DuckDB defaults | Auto-detects delimiter, headers, types; user can override conversationally |
| Table naming (CSV/Parquet) | Computed snake_case slug | Filename converted to valid unquoted DuckDB identifier |
| Glob patterns | User choice: separate or combined | Ask user whether to treat matched files as separate tables or single virtual table |
| Query execution model | In-memory DuckDB session | All queries use ATTACH IF NOT EXISTS for .ddb files, file paths for CSV/Parquet |
| ATTACH alias convention | `_db_` prefix + filename slug | `sales.ddb` → `AS _db_sales` for consistent, clear naming |

### Key Principles

1. **Never hallucinate columns** - Always validate against schema files before generating SQL
2. **Use existing assets first** - When `duckdb_sql_assets/` exists, READ the files; never regenerate schema unless explicitly requested
3. **User approval for all facts** - All AI-inferred facts require user approval via inline questions before dictionary entry
4. **Two-step query workflow** - Present plan for approval before writing SQL
5. **In-memory query execution** - All queries work in `duckdb` (no file argument); .ddb files use ATTACH IF NOT EXISTS with `_db_` prefix aliases
6. **Conversational setup** - Guide user through initial configuration
7. **Display-only by default** - Generate and display queries; only execute when user explicitly requests

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
├── tables_inventory.json    # Manifest: source files, file types, tables, columns
├── schema_<tablename>.sql   # One schema file per source (.ddb, .csv, .parquet, or glob)
└── data_dictionary.md       # Semantic documentation (editable by user)
```

---

## Workflows

### 1. Initial Setup (First Use)

When `duckdb_sql_assets/` doesn't exist:

1. Ask: "Which data files should I document?" (supports .ddb, .csv, .parquet, or glob patterns)
2. If glob pattern provided, ask: "Treat as separate tables or single combined table?"
3. Ask: "Do you have any code or documentation that explains this data?"
4. Generate assets:
   - `tables_inventory.json` via duckdb CLI (with file_type field)
   - `schema_<tablename>.sql` for each source:
     - `.ddb`: `duckdb file.ddb -c ".schema"`
     - `.csv`: `duckdb -c "DESCRIBE SELECT * FROM 'file.csv';"`
     - `.parquet`: `duckdb -c "DESCRIBE SELECT * FROM 'file.parquet';"`
   - Draft `data_dictionary.md` with rich structure (domains, table entries, relationships)
5. Run enum detection with hardcoded thresholds (max_cardinality=20, max_ratio=0.05, sample_size=10000)
6. Present findings:
   - If 1-2 enums: Ask inline per enum
   - If 3+ enums: Present bulk summary for approval
7. If approved, update `data_dictionary.md` directly with enum documentation

### 2. Query Generation

1. User asks for a query
2. Read `tables_inventory.json` and `data_dictionary.md`
3. **Step 1:** Present query plan (tables, joins, filters)
4. User approves plan
5. **Step 2:** Validate against schema files, generate SQL
6. If something new is learned, ask user if it should be added to the data dictionary

### 3. Schema Update Detection

Schema updates are on-demand only (triggered by user phrases like "refresh the schema" or "add file to assets").

- **Files removed:** Prompt to clean up assets
- **Files added:** User requests "add [file]", skill generates assets (supports .ddb, .csv, .parquet, or glob patterns)
- **Schema changes:** Detect new/removed columns, offer to update

Update actions:
- Removed files: Delete schema file, update inventory and dictionary
- Added files:
  - For .ddb: Generate schema via `.schema` command
  - For .csv/.parquet: Generate schema via `DESCRIBE SELECT * FROM 'file'`
  - For glob patterns: Ask user if separate tables or combined, then process accordingly
  - Update inventory (with file_type), add dictionary stubs, run enum detection
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
      "file_type": "ddb",
      "tables": ["table1", "table2"]
    },
    {
      "file_path": "/absolute/path/to/data.csv",
      "file_name": "data.csv",
      "file_type": "csv",
      "tables": ["data"]
    },
    {
      "file_path": "/absolute/path/to/events.parquet",
      "file_name": "events.parquet",
      "file_type": "parquet",
      "tables": ["events"]
    },
    {
      "file_path": "/absolute/path/to/logs/*.csv",
      "file_name": "logs/*.csv",
      "file_type": "csv_glob",
      "glob_pattern": "/absolute/path/to/logs/*.csv",
      "matched_files": ["jan.csv", "feb.csv"],
      "tables": ["logs"]
    }
  ],
  "tables": {
    "table1": {
      "source_file": "file.ddb",
      "file_type": "ddb",
      "columns": [
        {"name": "col1", "type": "VARCHAR"},
        {"name": "col2", "type": "INTEGER"}
      ]
    },
    "data": {
      "source_file": "data.csv",
      "file_type": "csv",
      "columns": [
        {"name": "id", "type": "INTEGER"},
        {"name": "value", "type": "VARCHAR"}
      ]
    }
  }
}
```

**File type values:**
- `ddb` - DuckDB database file (multiple tables, query via table name, cross-file via ATTACH)
- `csv` - Single CSV file (one table, query via file path)
- `parquet` - Single Parquet file (one table, query via file path)
- `csv_glob` - Multiple CSV files as single table (query via glob pattern)
- `parquet_glob` - Multiple Parquet files as single table (query via glob pattern)

**Table naming for CSV/Parquet:**
Convert filename to valid unquoted DuckDB identifier:
- Lowercase, snake_case
- Replace non-alphanumeric with underscore
- Strip extension
- Examples: `My Data-2024.csv` → `my_data_2024`, `Events.Log.parquet` → `events_log`

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

### For .ddb files

```bash
# Extract schema
duckdb file.ddb -c ".schema" > schema_file.sql

# List tables
duckdb file.ddb -c "SELECT table_name FROM information_schema.tables WHERE table_schema='main';"

# Describe table
duckdb file.ddb -c "DESCRIBE tablename;"

# Get column info
duckdb file.ddb -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name='tablename';"

# Get VARCHAR columns (for enum detection)
duckdb file.ddb -c "SELECT column_name, table_name FROM information_schema.columns WHERE table_schema='main' AND data_type IN ('VARCHAR', 'TEXT');"

# Check column cardinality (for enum detection)
duckdb file.ddb -c "WITH sampled AS (SELECT status FROM orders LIMIT 10000) SELECT COUNT(DISTINCT status) as distinct_count, COUNT(*) as sample_size FROM sampled;"

# Sample distinct values (for enum detection)
duckdb file.ddb -c "SELECT DISTINCT status FROM orders WHERE status IS NOT NULL LIMIT 25;"
```

### For .csv files

```bash
# Get inferred schema
duckdb -c "DESCRIBE SELECT * FROM '/path/to/file.csv';"

# Sample data
duckdb -c "SELECT * FROM '/path/to/file.csv' LIMIT 10;"

# Check column cardinality (for enum detection)
duckdb -c "WITH sampled AS (SELECT status FROM '/path/to/file.csv' LIMIT 10000) SELECT COUNT(DISTINCT status) as distinct_count, COUNT(*) as sample_size FROM sampled;"

# Sample distinct values (for enum detection)
duckdb -c "SELECT DISTINCT status FROM '/path/to/file.csv' WHERE status IS NOT NULL LIMIT 25;"

# With explicit options (if auto-detect fails)
duckdb -c "SELECT * FROM read_csv('/path/to/file.csv', header=true, delim=',');"
```

### For .parquet files

```bash
# Get embedded schema
duckdb -c "DESCRIBE SELECT * FROM '/path/to/file.parquet';"

# Sample data
duckdb -c "SELECT * FROM '/path/to/file.parquet' LIMIT 10;"

# Check column cardinality (for enum detection)
duckdb -c "WITH sampled AS (SELECT category FROM '/path/to/file.parquet' LIMIT 10000) SELECT COUNT(DISTINCT category) as distinct_count, COUNT(*) as sample_size FROM sampled;"
```

### General

```bash
# Check version
duckdb -version

# Expand glob pattern
ls /path/to/logs/*.csv
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
| Multi-file | `ATTACH IF NOT EXISTS 'file.ddb' AS _db_alias (READ_ONLY)` | N/A |

### Multi-File Query Patterns

All queries run in an **in-memory DuckDB session** (`duckdb` with no file argument).

**Single .ddb file:**
```sql
ATTACH IF NOT EXISTS '/path/to/sales.ddb' AS _db_sales (READ_ONLY);

SELECT * FROM _db_sales.customers;
```

**Multiple .ddb files:**
```sql
ATTACH IF NOT EXISTS '/path/to/sales.ddb' AS _db_sales (READ_ONLY);
ATTACH IF NOT EXISTS '/path/to/inventory.ddb' AS _db_inventory (READ_ONLY);

SELECT c.name, o.total_amount, p.name AS product_name
FROM _db_sales.customers c
JOIN _db_sales.orders o ON c.customer_id = o.customer_id
JOIN _db_inventory.products p ON o.product_id = p.product_id;
```

**CSV/Parquet files (direct file paths, no ATTACH):**
```sql
SELECT * FROM '/path/to/orders.csv' o
JOIN '/path/to/customers.parquet' c ON o.customer_id = c.id;
```

**Mixed .ddb + CSV/Parquet:**
```sql
ATTACH IF NOT EXISTS '/path/to/sales.ddb' AS _db_sales (READ_ONLY);

SELECT c.name, t.amount
FROM _db_sales.customers c
JOIN '/path/to/transactions.csv' t ON c.customer_id = t.customer_id;
```

**Glob patterns (multiple files as single table):**
```sql
SELECT * FROM '/path/to/logs/*.csv';
SELECT * FROM read_csv('/path/to/data/*.csv', union_by_name=true);
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

**Cross-file join example:** In an in-memory session, use `ATTACH IF NOT EXISTS '/path/to/sales.ddb' AS _db_sales (READ_ONLY)` then reference tables as `_db_sales.orders`, `_db_sales.customers`.

### CSV Test Files

**transactions.csv**:
```csv
transaction_id,customer_id,amount,transaction_date,status
1001,1,99.99,2024-03-01,completed
1002,1,149.50,2024-03-15,completed
1003,2,75.00,2024-03-20,pending
1004,2,200.00,2024-03-25,cancelled
```

**products.csv**:
```csv
product_id,name,category,price
1,Widget A,Electronics,29.99
2,Gadget B,Electronics,49.99
3,Tool C,Hardware,19.99
```

### Parquet Test Files

Create Parquet files from CSV using DuckDB:
```bash
# Convert CSV to Parquet
duckdb -c "COPY (SELECT * FROM 'transactions.csv') TO 'transactions.parquet' (FORMAT PARQUET);"
duckdb -c "COPY (SELECT * FROM 'products.csv') TO 'products.parquet' (FORMAT PARQUET);"
```

### Mixed File Type Testing

Test queries across file types (all run in in-memory session):
```sql
-- Attach DuckDB database, join to CSV
ATTACH IF NOT EXISTS 'sales.ddb' AS _db_sales (READ_ONLY);

SELECT c.name, t.amount
FROM _db_sales.customers c
JOIN 'transactions.csv' t ON c.customer_id = t.customer_id;

-- Join CSV to Parquet (no ATTACH needed)
SELECT t.*, p.name as product_name
FROM 'transactions.csv' t
JOIN 'products.parquet' p ON t.product_id = p.product_id;
```

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
| tables_inventory.json | Manifest of source files, file types, and tables |
| schema_*.sql | One schema file per source (.ddb, .csv, .parquet, or glob) |
| data_dictionary.md | Semantic documentation (editable by user) |
