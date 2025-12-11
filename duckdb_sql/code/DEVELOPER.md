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
| Enum detection | Auto-detect via sampling with configurable thresholds | Happy path: defaults work; power users can tune |
| Statistics | Schema-only (no row counts) | Prevents stale data; schema changes less frequently |
| Cross-file relationships | Not auto-created | Discovered through usage, captured in OBSERVATIONS.md |
| Fact collection | Via OBSERVATIONS.md | All inferred facts require user approval before dictionary entry |
| Bulk approval | Supported | User can approve multiple observations at once |
| Query execution | Display-only by default | Users review/copy queries; execution only on explicit request |

### Key Principles

1. **Never hallucinate columns** - Always validate against schema files before generating SQL
2. **User approval for all facts** - Even AI-inferred facts from supplementary docs go to OBSERVATIONS.md first
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
├── data_dictionary.md       # Semantic documentation
└── OBSERVATIONS.md          # Staging area for learned facts
```

---

## Workflows

### 1. Initial Setup (First Use)

When `duckdb_sql_assets/` doesn't exist:

1. Ask: "Which .ddb files should I document?"
2. Ask: "Do you have any code or documentation that explains this data?"
3. Generate assets:
   - `tables_inventory.json` via duckdb CLI (includes default enum detection config)
   - `schema_<filename>.sql` for each database
   - Draft `data_dictionary.md` with rich structure (domains, table entries, relationships)
   - `OBSERVATIONS.md` with AI-inferred facts
4. Run enum detection (see below) and add results to OBSERVATIONS.md
5. Present OBSERVATIONS.md for bulk review
6. Merge approved observations into dictionary

### 2. Query Generation

1. User asks for a query
2. Read `tables_inventory.json` and `data_dictionary.md`
3. **Step 1:** Present query plan (tables, joins, filters)
4. User approves plan
5. **Step 2:** Validate against schema files, generate SQL
6. If something new is learned, add to OBSERVATIONS.md

### 3. Schema Update Detection

On skill invocation, check for changes:

- **Files removed:** Prompt to clean up assets
- **Files added:** User requests "add new_file.ddb", skill generates assets
- **Schema changes:** Detect new/removed columns, offer to update

Update actions:
- Removed files: Delete schema file, update inventory and dictionary
- Added files: Generate schema, update inventory, add dictionary stubs, infer observations
- Schema changes: Regenerate schema file, update inventory

### 4. Observation Approval

1. User edits OBSERVATIONS.md, checking `[x]` for approved facts
2. User says "merge approved observations"
3. Skill moves approved facts to `data_dictionary.md`
4. Facts archived in "## Merged" section with date

### 5. Enum Detection

During setup and on-demand, the skill scans for likely enum columns.

**Happy Path:** Defaults work automatically for most datasets. User just reviews and approves observations.

### 6. Consolidate/Package Dataset

See dedicated section below for full details. Summary:
1. User triggers with "package this data set" or similar
2. Skill prompts for output directory and database name
3. Creates subdirectory with single .ddb file containing all tables
4. Generates fresh assets pointing to consolidated file
5. Original files remain untouched

**Configuration** (in `tables_inventory.json`):
```json
{
  "enum_detection": {
    "max_cardinality": 20,
    "max_ratio": 0.05,
    "sample_size": 10000,
    "name_patterns": ["status", "type", "state", "category", "level", "role", "kind"]
  }
}
```

| Setting | Default | Description |
|---------|---------|-------------|
| `max_cardinality` | 20 | Max distinct values to consider as enum |
| `max_ratio` | 0.05 | Max ratio of distinct/total rows (5%) |
| `sample_size` | 10000 | Rows to sample per table |
| `name_patterns` | [...] | Column name patterns that suggest enums |

**Detection Heuristics:**
A column is flagged as likely enum if ALL are true:
1. Type is VARCHAR or TEXT
2. `distinct_count <= max_cardinality`
3. `distinct_count / sampled_rows < max_ratio`

**Re-running:** User edits config in `tables_inventory.json`, then says "re-run enum detection".

---

## Asset File Formats

### tables_inventory.json

```json
{
  "generated_at": "2025-12-11T17:30:00Z",
  "duckdb_version": "v1.3.2",
  "enum_detection": {
    "max_cardinality": 20,
    "max_ratio": 0.05,
    "sample_size": 10000,
    "name_patterns": ["status", "type", "state", "category", "level", "role", "kind"]
  },
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

### OBSERVATIONS.md

```markdown
# Observations

## Pending Approval

### YYYY-MM-DD
- [ ] Fact 1 about the data
- [ ] Fact 2 about relationships
- [x] Approved fact (ready to merge)

## Approved (to be merged)
[Facts checked off, awaiting merge command]

## Merged
[Historical record with dates]
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

## Consolidate/Package Dataset Workflow

This workflow allows users to create a deliverable snapshot of their multi-file setup.

### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Original files | Preserved | Users continue working with multi-file setup; package is for delivery |
| Output location | Subdirectory in cwd | Self-contained, easy to zip and share |
| Database naming | Derived from project | Sensible default, user confirms |
| Conflict resolution | Prefix with source name | Preserves all data, makes origin clear |
| Assets | Full regeneration | Clean slate for packaged version |

### DuckDB Commands

```bash
# Create consolidated database using ATTACH + CREATE TABLE AS SELECT
duckdb /output/project.ddb << 'EOF'
ATTACH '/path/to/sales.ddb' AS src_sales (READ_ONLY);
ATTACH '/path/to/inventory.ddb' AS src_inv (READ_ONLY);

CREATE TABLE customers AS SELECT * FROM src_sales.customers;
CREATE TABLE orders AS SELECT * FROM src_sales.orders;
CREATE TABLE products AS SELECT * FROM src_inv.products;
CREATE TABLE stock AS SELECT * FROM src_inv.stock;

DETACH src_sales;
DETACH src_inv;
EOF

# Generate schema for new database
duckdb /output/project.ddb -c ".schema" > /output/duckdb_sql_assets/schema_project.sql
```

### Asset Transformations

**tables_inventory.json:**
- `sources[]`: Collapses to single entry with relative path `./project.ddb`
- `tables{}`: All `source_file` fields updated to new filename
- New `packaged_from` object added for provenance

**data_dictionary.md:**
- Header: Update `**Source Files:**` to single file
- Header: Add `**Packaged from:**` for provenance
- Each table: Update `**Source file:**` line
- Each table: Add `**Original source:**` for provenance
- If conflicts resolved via prefix: Update table names and "Also known as"

**schema_*.sql:**
- Delete all old schema files
- Generate single `schema_<name>.sql` from consolidated database

**OBSERVATIONS.md:**
- Fresh template with packaging provenance note

### Table Name Conflict Handling

Detection: Build `table_name -> [source_files]` map, flag duplicates.

Resolution options:
1. **Prefix** (default): `sales_users`, `support_users`
2. **Skip**: Keep first occurrence only
3. **Abort**: Cancel for manual resolution

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
| data_dictionary.md | Semantic documentation |
| OBSERVATIONS.md | Staging area for learned facts |
