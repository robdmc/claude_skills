# Scribe — A Work Log for Exploratory Projects

Scribe is a Claude Code skill that keeps a running narrative log of your exploratory work. Instead of losing track of what you tried, why it failed, and what finally worked, the scribe captures it all in plain markdown files you can read anytime.

## What It Does

- **Logs your work** — Narrative entries describing what you did, what worked, what didn't
- **Snapshots files** — Archives versions of files at meaningful moments (before risky changes, when something finally works)
- **Answers questions** — "What did we try for the null problem?" "Where did we leave off?"
- **Tracks threads** — Links related entries so you can trace an investigation from start to finish

## Installation

Place the `scribe/` folder in your Claude Code skills directory:

```
~/.claude/skills/scribe/
├── SKILL.md
└── scripts/
    ├── entry.py
    ├── assets.py
    └── validate.py
```

## Usage

Just talk to the scribe naturally during your Claude Code session:

### Logging

```
"hey scribe, log this"
"scribe, we just figured out the bug — it was timezone handling"
"scribe — this was a dead end, log it"
"scribe, quick log: fixed the off-by-one error"
```

The scribe will propose an entry for you to review before writing. For quick logs, it writes directly.

### Archiving Files

```
"scribe, save this notebook"
"scribe, snapshot the ETL script before I refactor"
"scribe, archive clustering.ipynb — this is the first version that works"
```

Files are copied to `.scribe/assets/` and linked in the log entry.

### Restoring Files

```
"scribe, restore the notebook from before the refactor"
"scribe, run the ETL script we saved last Tuesday"
```

Restored files appear next to the current version with an underscore prefix (e.g., `_2026-01-23-14-35-clustering.ipynb`) for easy comparison.

### Querying

```
"scribe, what did we do today?"
"scribe, what did we try for the null problem?"
"scribe, where did we leave off?"
"scribe, what's still unresolved?"
"scribe, summarize last week"
```

### Slash Commands

If you prefer explicit commands:

```
/scribe                              — log an entry
/scribe save clustering.ipynb        — log and archive a file
/scribe ask what did we try?         — query the logs
```

## What Gets Created

The scribe creates a `.scribe/` directory in your project:

```
.scribe/
├── 2026-01-23.md          # Daily log file
├── 2026-01-24.md          # One file per day
└── assets/
    ├── 2026-01-23-14-35-clustering.ipynb
    └── 2026-01-24-09-15-etl.py
```

**Log files** are append-only markdown. Each entry has a timestamp, title, narrative, and status.

**Assets** are snapshots of files, named with the entry ID that archived them.

## Example Entry

```markdown
## 14:35 — Fixed null handling in ETL pipeline
<!-- id: 2026-01-23-14-35 -->

Found that nulls originated from the 2019 migration. The legacy system used 
empty strings, but the new schema expects actual NULLs. Updated `etl.py` to 
coalesce empty strings to NULL for pre-2019 records.

**Files touched:**
- `etl.py` — Added coalesce logic in transform step
- `exploration.ipynb` — Validated fix on sample data

**Archived:**
- `src/etl/pipeline.py` → [`2026-01-23-14-35-pipeline.py`](assets/2026-01-23-14-35-pipeline.py) — Before null fix

**Status:** Ready for full validation on production dataset

---
```

## Linking Related Entries

When you're following up on previous work, the scribe links entries together:

```
"scribe, the timezone hypothesis was a dead end — link back to those entries"
"scribe, this connects to the null handling work from yesterday"
```

Entries include a **Related** section that lets you trace investigations:

```markdown
**Related:** 2026-01-23-14-35 — Fixed null handling in ETL pipeline
```

## Tips

- **Log at natural breakpoints** — When you solve something, hit a dead end, or stop for the day
- **Let the scribe propose first** — It captures context you might forget to mention
- **Use "dead end" annotations** — Failed approaches are valuable to record
- **Snapshot before risky changes** — Easy to compare or revert
- **Ask questions when returning** — "Where did we leave off?" gets you back up to speed

## Limitations

- **Single session** — Not designed for multiple Claude sessions writing simultaneously
- **Project scale** — Best for weeks-to-months of work, not permanent archives
- **Plain text** — Logs are markdown; no database, no sync, no cloud

## Files

The skill consists of:

| File | Purpose |
|------|---------|
| `SKILL.md` | Instructions for Claude |
| `scripts/entry.py` | Writes and edits log entries |
| `scripts/assets.py` | Archives and restores file snapshots |
| `scripts/validate.py` | Checks log consistency |

You don't need to run these scripts directly — Claude handles that. But they're plain Python if you want to inspect or modify them.
