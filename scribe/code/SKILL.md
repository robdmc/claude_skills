---
name: scribe
description: Maintains a narrative log of exploratory work with file archives. Capabilities: (1) Log entries with propose-confirm flow, (2) Archive files linked to entries, (3) Restore archived files, (4) Query past work by time or topic, (5) Link related entries for thread tracking. Activates when user addresses "scribe" directly (e.g., "hey scribe, log this", "scribe, save this notebook", "scribe, what did we try yesterday?") or uses `/scribe` commands.
allowed-tools: Read, Write, Bash(python:*), Bash(mkdir:*), Bash(git:*), Glob, Grep
argument-hint: [log | save <file> | restore <asset> | ask <question>]
---

# Scribe

The scribe maintains a narrative log of your exploratory work and can archive important files.

**Address naturally:** "hey scribe, log this" / "scribe, save this notebook" / "scribe, what did we try yesterday?"

**Or use commands:** `/scribe` / `/scribe save file.py` / `/scribe ask what happened last week?`

## Quick Reference

| Mode | Trigger | Action |
|------|---------|--------|
| Log | "scribe, log this" | Propose entry → confirm → write |
| Quick log | "scribe, quick log: fixed bug" | Write directly |
| Archive | "scribe, save notebook.ipynb" | Log + archive file |
| Restore | "scribe, restore the ETL script" | Copy from assets |
| Query | "scribe, what did we try?" | Search and summarize |

## Directory Structure

```
.scribe/
├── 2026-01-23.md      # Daily log files
└── assets/            # Archived files
    └── 2026-01-23-14-35-notebook.ipynb
```

## Scripts

Scripts in `{SKILL_DIR}/scripts/` (substitute actual path when invoking):

| Script | Purpose |
|--------|---------|
| `entry.py write --file /tmp/entry.md` | Write entry from temp file |
| `entry.py last` | Get last entry ID from today |
| `assets.py save <id> <file>` | Archive a file |
| `assets.py list [filter]` | List archived files |
| `assets.py get <asset> --dest <dir>` | Restore a file |
| `validate.py` | Check for errors |

**Python 3.9+ required.**

## Logging Flow

1. **Assess** — Check conversation context, recent logs, `git status`
2. **Propose** — Draft entry, offer optional file archives
3. **Confirm** — Wait for user approval
4. **Write** — `python {SKILL_DIR}/scripts/entry.py write --file /tmp/scribe_entry.md`

**Shortcut:** For "quick log", write directly without proposing.

### Entry Format

Write to `/tmp/scribe_entry.md`:
```markdown
## Brief title here

What happened, why, what was tried.

**Files touched:**
- `file.py` — What changed

**Status:** Current state

---
```

The script adds timestamp and ID automatically.

## Entry IDs

Format: `YYYY-MM-DD-HH-MM` (e.g., `2026-01-23-14-35`). Collisions get `-02`, `-03` suffix.

IDs link entries to assets and enable **Related** cross-references:
```markdown
**Related:** 2026-01-23-14-35 — Previous entry title
```

## Archiving

After writing entry, archive files:
```bash
python {SKILL_DIR}/scripts/assets.py save 2026-01-23-14-35 notebook.ipynb
```

Add to entry:
```markdown
**Archived:**
- `src/notebook.ipynb` → [`2026-01-23-14-35-notebook.ipynb`](assets/2026-01-23-14-35-notebook.ipynb)
```

## Querying

- **Time-based:** Read `.scribe/YYYY-MM-DD.md` directly
- **Topic-based:** `Grep` in `.scribe/`, then Read matches
- **Assets:** `python {SKILL_DIR}/scripts/assets.py list [filter]`

## Orientation (New Sessions)

1. Read today's log file
2. Run `git status` to see changes
3. Ask user what to capture

## Initialization

On first use:
```bash
mkdir -p .scribe/assets
```

Add to `.gitignore`:
```
.scribe/
_20*-*
```

## Reference Files

For detailed examples and edge cases, see:
- [reference/logging.md](reference/logging.md) — Entry formats, examples
- [reference/archiving.md](reference/archiving.md) — Archive/restore details
- [reference/querying.md](reference/querying.md) — Query patterns
- [reference/recovery.md](reference/recovery.md) — Error recovery, edit commands

## Principles

- **Narrator, not stenographer** — Write prose, not dumps
- **Capture the why** — Not just what, but why it was tried
- **Stay concise** — Entries should be scannable
- **Preserve dead ends** — Failed approaches prevent repeats
