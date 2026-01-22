---
name: viz
description: Visualization factory that generates matplotlib/seaborn plotting functions. Use when you need a function to create a specific visualization. Provide a natural language spec describing the plot type, data context, axis labels, title, and any special requirements. Returns executable Python function code.
allowed-tools: Read, Glob(/tmp/viz/*), Grep(/tmp/viz/*), Bash(python /Users/rob/.claude/skills/viz/viz_runner.py:*)
---

# Viz Skill: Direct Execution Visualization

## Purpose

This skill **directly executes** visualizations. The calling agent provides a visualization spec along with data context, and the skill:
1. Infers the data loading code from the provided context
2. Generates the complete plotting script
3. Executes it via the `viz_runner.py` helper
4. Returns artifact paths for the caller to reference

**Key pattern:**
```
Caller (with data context) → Skill (infers data loading, generates script, executes) → Plot appears
```

The caller does NOT need to write any execution code. The skill handles everything.

## Input Specification

The calling agent should provide:

### Required
- **Visualization spec**: What to plot (chart type, axes, title, special features)

### Data Context (one of these forms)
- **Database + query**: "Data from `operational_forecast.ddb`, table `forecast`, columns month, members"
- **SQL query**: "Run this SQL: `SELECT * FROM forecast WHERE year >= 2024`"
- **Code snippet**: "Load data like this: `df = pd.read_parquet('data.parquet')`"
- **File path**: "CSV at `/tmp/data.csv` with columns X, Y, Z"

### Optional
- **Suggested ID**: A name hint (e.g., `pop_bar`, `churn_trend`). The runner ensures uniqueness.

## Artifact Management

All artifacts are managed in `/tmp/viz/` via the helper script.

### Helper: `viz_runner.py`

```bash
python /Users/rob/.claude/skills/viz/viz_runner.py [--id NAME] [--desc "Description"] << 'EOF'
<generated script>
EOF
```

The runner:
1. Creates `/tmp/viz/` if needed
2. Ensures ID uniqueness (appends `_2`, `_3`, etc. if collision)
3. Injects `plt.savefig('/tmp/viz/<id>.png', dpi=150, bbox_inches='tight')` before `plt.show()`
4. Writes the script to `/tmp/viz/<id>.py`
5. Executes the script
6. Writes metadata to `/tmp/viz/<id>.json`
7. Prints human-readable results to stdout

### Output Format

Terminal output:
```
Plot: pop_bar
  "Bar chart of members by month"
  png: /tmp/viz/pop_bar.png
```

Sidecar JSON (`/tmp/viz/<id>.json`):
```json
{
  "id": "pop_bar",
  "desc": "Bar chart of members by month",
  "png": "/tmp/viz/pop_bar.png",
  "script": "/tmp/viz/pop_bar.py",
  "created": "2025-01-22T11:31:00",
  "pid": 46368
}
```

The caller can then:
- Read the PNG into context to discuss the plot
- Reference the script for modifications
- Look up plots by ID or description via the JSON metadata

## Skill Workflow

1. **Infer data loading**: From the provided context, generate Python code to load/create the DataFrame
2. **Generate visualization**: Add matplotlib/seaborn code for the requested plot
3. **Execute via runner** (always include `--desc` with a short summary):
   ```bash
   python /Users/rob/.claude/skills/viz/viz_runner.py --id suggested_name --desc "Short description of plot" << 'EOF'
   <complete script>
   EOF
   ```
4. **Parse output**: Capture the ID and paths from stdout
5. **Return to caller**: Report final ID and paths

## Library Selection

### Use Seaborn When:
- Statistical distributions (histogram + KDE, violin, box plots)
- Regression with confidence intervals
- Categorical comparisons with error bars
- Heatmaps and correlation matrices

### Use Matplotlib When:
- Fine-grained control over appearance
- Time series with date formatting
- Custom annotations and reference lines
- Simple plots without statistical features

### Combine Both:
Use seaborn for the statistical plot, matplotlib for customizations like reference lines.

## Publication Quality Standards

- **Labels**: Descriptive axis labels with units, 12pt+ font
- **Titles**: Clear, informative, 14pt+ font
- **Figure size**: `figsize=(10, 6)` or appropriate aspect ratio
- **Layout**: Always use `tight_layout()` to prevent clipping
- **Grids**: Subtle guidance with `alpha=0.3`
- **Colors**: Colorblind-friendly palettes (viridis, coolwarm, Set2)
- **Transparency**: Alpha for overlapping points
- **Imports**: Inside the script for self-contained execution

## End-to-End Example

**Request from caller:**
```
/viz id=pop_bar
     bar chart showing total_initial_members and total_final_members by month
     with dashed vertical line at history/forecast boundary (Dec 2025 / Jan 2026).
     Data from operational_forecast.ddb, forecast table.
```

**Skill generates and executes:**
```bash
python /Users/rob/.claude/skills/viz/viz_runner.py --id pop_bar --desc "Bar chart of members by month with forecast boundary" << 'EOF'
import duckdb
import matplotlib.pyplot as plt
import numpy as np

# Load data from DuckDB
con = duckdb.connect('/path/to/operational_forecast.ddb', read_only=True)
df = con.execute("""
    SELECT month, total_initial_members, total_final_members
    FROM forecast
    ORDER BY month
""").df()
con.close()

# Create grouped bar chart
fig, ax = plt.subplots(figsize=(12, 6))
x = np.arange(len(df))
width = 0.35

bars1 = ax.bar(x - width/2, df['total_initial_members'], width, label='Initial Members', color='steelblue')
bars2 = ax.bar(x + width/2, df['total_final_members'], width, label='Final Members', color='coral')

# History/forecast boundary
boundary_idx = df[df['month'] == '2025-12'].index[0] + 0.5
ax.axvline(x=boundary_idx, color='gray', linestyle='--', linewidth=1.5, label='Forecast Start')

ax.set_xlabel('Month', fontsize=12)
ax.set_ylabel('Members', fontsize=12)
ax.set_title('Member Population by Month: Historical vs Forecast', fontsize=14)
ax.set_xticks(x)
ax.set_xticklabels(df['month'], rotation=45, ha='right')
ax.legend()
ax.grid(True, alpha=0.3, axis='y')
plt.tight_layout()
plt.show()
EOF
```

**Runner output:**
```
Plot: pop_bar
  "Bar chart of members by month with forecast boundary"
  png: /tmp/viz/pop_bar.png
```

**Skill returns to caller:**
> Plot generated successfully.
> - ID: `pop_bar`
> - Script: `/tmp/viz/pop_bar.py`
> - PNG: `/tmp/viz/pop_bar.png`

The caller can then read the PNG into context for discussion or reference the script for modifications.

## Refinement Workflow

When refining an existing plot:

1. Caller provides the existing script path + requested changes
2. Skill reads the script, applies modifications
3. Executes with a new ID (e.g., `pop_bar_2`)
4. Both versions remain available for comparison

## Interactive Backend Note

Generated scripts use `plt.show()` which works with the `macosx` backend for interactive display. The injected `savefig()` ensures a PNG copy is always saved before display.
