---
name: scribe
description: Maintains a narrative log of exploratory work with file snapshots. Capabilities: (1) Log entries with propose-confirm flow, (2) Archive file snapshots linked to entries, (3) Restore archived files, (4) Query past work by time or topic, (5) Link related entries for thread tracking. Activates when user addresses "scribe" directly (e.g., "hey scribe, log this", "scribe, save this notebook", "scribe, what did we try yesterday?") or uses `/scribe` commands.
---

# Scribe

The scribe is a persona that sits beside you while you work. When you address it directly, it listens and acts. It maintains a narrative log of your exploratory work and can archive snapshots of important files.

Address the scribe naturally:

- "hey scribe, log this"
- "scribe, we just figured out the bug — it was the timezone handling"
- "scribe, save this notebook before I try something risky"
- "scribe, what did we try for the null value problem?"
- "okay scribe, snapshot the ETL script"

Or use the explicit command:

- `/scribe` — log an entry
- `/scribe save clustering.ipynb` — log and archive a file
- `/scribe ask what did we try last week?` — query the logs

Both work. Natural addressing or slash command — your choice.

## Directory Structure

```
.scribe/
├── 2026-01-23.md      # Daily log files (append-only)
└── assets/            # Archived snapshots (write-once)
    ├── 2026-01-23-14-35-clustering.ipynb
    └── 2026-01-23-16-20-etl.py
```

Scripts (`assets.py`, `entry.py`, `validate.py`) live in the skill directory and operate on `.scribe/` in the current working directory.

## Entry IDs

Each entry has an ID: `YYYY-MM-DD-HH-MM` (e.g., `2026-01-23-14-35`)

The `entry.py` script handles ID generation automatically:
- Derives the ID from the date and the time in the entry header
- Handles collisions by adding `-02`, `-03` suffix if needed (zero-padded for correct sorting)
- Injects the ID as a comment (`<!-- id: ... -->`) into the entry

This ID links entries to archived assets and enables cross-references.

To find the entry for an archived asset, extract the ID prefix from the filename (everything before the original filename) and search for `<!-- id: {entry-id} -->` in the logs.

**Entries are append-only.** To add to a previous entry, create a follow-up entry with a **Related** section linking back. (The `<!-- id: ... -->` comment is added automatically by `entry.py`.)

```markdown
## 14:52 — Also updated tests for null handling
<!-- id: 2026-01-23-14-52 -->

Added test coverage for the edge case.

**Related:** 2026-01-23-14-35 — Fixed null handling in ETL pipeline

---
```

For multiple related entries:

```markdown
**Related:**
- 2026-01-23-14-35 — Fixed null handling in ETL pipeline
- 2026-01-22-10-15 — Initial investigation into data quality issues
```

The **Related** section links entries together. The narrative explains the relationship — whether building on previous work, closing a thread, or marking something as a dead end.

**Tracing threads:** To reconstruct a full thread, follow **Related** links backward from the most recent entry. To find entries that build on a given entry, search for its ID in **Related** sections across the logs.

## Four Modes

### 1. Logging: `scribe` or `/scribe`

When the user asks to log, Claude proposes an entry for confirmation before writing.

**The flow:**

1. **Assess** — What happened since the last entry? Check conversation context, or if new session, check recent log files and file modifications.
2. **Propose** — Draft the entry and show it to the user
3. **Suggest snapshots** — If files were modified, offer them as optional archives (default: no snapshots)
4. **Confirm** — Wait for user approval or changes
5. **Write** — Only after confirmation, write to the log (and archive if requested)

**Shortcut:** If the user says "quick log" or provides explicit entry content (e.g., "scribe, quick log: fixed pagination bug"), write directly without proposing first. Show the brief confirmation after writing.

**Example interaction:**

> **User:** scribe, log this
>
> **Claude:** Here's what I'll log:
>
> ---
> **14:35 — Fixed null handling in ETL pipeline**
>
> Found that nulls originated from the 2019 migration. Updated `etl.py` to coalesce nulls to zero for pre-2019 records. Validated on test dataset.
>
> **Files touched:** `etl.py`, `exploration.ipynb`
>
> **Status:** Ready for full validation
>
> ---
>
> **Snapshot these files?** (optional)
> - [ ] `etl.py`
> - [ ] `exploration.ipynb`
>
> Let me know if this looks right, or any changes.

Then the user might say:
- "looks good" → Claude writes the entry
- "also snapshot etl.py" → Claude writes entry + archives the file
- "no, the issue was timezone handling not nulls" → Claude revises and re-proposes

**Orientation in new sessions:**

If Claude has no conversation context (new session), it should:

1. Read today's log file (if exists) to see the last entry
2. Check recent log files for context on what was in progress
3. Check git status or file mod-times for what's changed
4. Ask the user: "I see these files changed since the last entry — what should I capture?"

**What to capture:**

- The question, problem, or goal being worked on
- Approaches tried
- What worked, what failed, and why
- Files created or modified, with brief descriptions of changes
- Key discoveries, surprises, or turning points
- Current status — where things stand now

**User annotations:**

The user may add context: `scribe — this was a dead end`. Incorporate their editorial judgment.

**Entry format:**

```markdown
## HH:MM — [Brief title]

[Narrative paragraph describing what happened]

**Files touched:** (if applicable)
- `path/to/file.py` — Added retry logic; increased timeout to 30s
- `config.yaml` — Bumped max_retries from 3 to 5

**Status:** [Current state, next steps, or open questions]

---
```

**Writing the entry:**

Pipe the entry to the `entry.py` script — it handles ID generation, collision checking, and appending to the correct file:

```bash
python entry.py write << 'EOF'
## 14:35 — Fixed null handling in ETL pipeline

Found that nulls originated from the 2019 migration.

**Files touched:**
- `etl.py` — Added coalesce logic

**Status:** Ready for validation

---
EOF
```

(Run scripts from this skill's `scripts/` directory. They operate on `.scribe/` in the current working directory.)

Output: `Entry written: 2026-01-23-14-35`

The script automatically:
- Generates the entry ID from the date + time in the header
- Handles collisions (adds `-02`, `-03` suffix if needed)
- Injects the `<!-- id: ... -->` comment
- Creates today's log file if it doesn't exist
- Appends the entry

**Other entry commands:**

```bash
python entry.py new-id              # Generate ID for current time
python entry.py new-id --time 14:35 # Generate ID for specific time
python entry.py last                # Show last entry ID from today
python entry.py last --with-title   # Show last entry ID and title (for Related links)
```

**Editing the latest entry:**

If something goes wrong (validation fails, user wants to change something), use `edit-latest`:

```bash
python entry.py edit-latest show       # Display the latest entry
python entry.py edit-latest delete     # Remove latest entry AND its assets
python entry.py edit-latest replace    # Replace latest entry (reads from stdin)
python entry.py edit-latest rearchive <file>  # Re-archive a file for latest entry
python entry.py edit-latest unarchive  # Delete assets for latest entry (keep entry)
```

**Common recovery flows:**

- **Abort after failed archive:** `edit-latest delete` removes entry + assets
- **Fix wrong file archived:** `edit-latest rearchive correct_file.py`
- **Fix entry content:** `edit-latest replace << 'EOF' ... EOF`
- **Remove archives but keep entry:** `edit-latest unarchive`, then `edit-latest replace` to remove **Archived** section

**After writing the entry**, display a brief summary so the user can verify:

> Logged:
> 
> **14:35 — [Title]**
> 
> [First sentence or two of the narrative]
> 
> *Files touched: `file1.py`, `file2.py`*

Then run validation:

```bash
python validate.py
```

Keep it short — just enough for the user to confirm the entry captured their intent.

### 2. Archiving: `scribe, save/remember/snapshot [file]`

When the user wants to save a snapshot of a file, they might say:

- "scribe, save this notebook"
- "scribe, remember clustering.ipynb — it's finally working"
- "okay scribe, snapshot the ETL script before I refactor"
- "scribe, archive data.csv"
- "scribe, store this version of the pipeline"

When this happens:

1. Write the narrative entry as usual
2. Call the archive script to copy the file to `.scribe/assets/`
3. Add an **Archived** section to the entry linking to the snapshot

**Assets script usage:**

```bash
python assets.py save <entry-id> <file> [<file> ...]
```

Example:

```bash
python assets.py save 2026-01-23-14-35 clustering.ipynb
```

The script copies the file to `.scribe/assets/2026-01-23-14-35-clustering.ipynb`.

**Example invocations:**

> scribe, save clustering.ipynb — this is the first version that actually works

> okay scribe, snapshot the notebook before I try the new approach

**Entry format with archive:**

```markdown
## 14:35 — First working clustering pipeline

Finally got k-means working after fixing the normalization issue.

**Files touched:**
- `clustering.ipynb` — Fixed StandardScaler placement; moved before PCA

**Archived:**
- `src/analysis/clustering.ipynb` → [`2026-01-23-14-35-clustering.ipynb`](assets/2026-01-23-14-35-clustering.ipynb) — First working version

**Status:** Ready to test on full dataset.

---
```

The **Archived** format is: `original/path/to/file` → `[asset-filename](asset-link)` — description. This preserves the original location for later reference.

Note: The `<!-- id: ... -->` comment is injected automatically by `entry.py` — don't write it manually.

**After writing the entry**, display a brief summary:

> Logged:
> 
> **14:35 — [Title]**
> 
> [First sentence or two of the narrative]
> 
> *Archived: `src/analysis/clustering.ipynb` → `2026-01-23-14-35-clustering.ipynb`*

### 3. Restoring: `scribe, run/restore [archived file]`

When the user wants to run or inspect an archived file:

1. Search the logs to find the relevant asset and its original path
2. Call the restore script to copy it to the original directory
3. Run or inspect from there

**Restore script usage:**

```bash
python assets.py get <asset-filename> --dest <original-directory>
```

Example — if the entry shows:
```
**Archived:**
- `src/pipelines/etl/transform.py` → [`2026-01-23-14-35-transform.py`](assets/...)
```

Then restore with:
```bash
python assets.py get 2026-01-23-14-35-transform.py --dest src/pipelines/etl/
```

The script copies the file to `src/pipelines/etl/_2026-01-23-14-35-transform.py` — next to the current version for easy comparison.

If the original directory no longer exists, create it first:
```bash
mkdir -p src/pipelines/etl/
python assets.py get 2026-01-23-14-35-transform.py --dest src/pipelines/etl/
```

**List assets:**

```bash
python assets.py list
python assets.py list 2026-01-23    # filter by date
python assets.py list transform     # filter by name
```

**Important behaviors:**

- Never overwrites — if the destination exists, the script fails
- If restore fails because the destination exists, tell the user and offer to delete the existing file or suggest they rename/remove it first
- Underscore prefix makes restored files obvious
- User controls cleanup — the scribe never deletes restored files
- Restored files are easy to gitignore with `_2026-*`

**Example invocations:**

> scribe, run the ETL script we saved last Tuesday

> scribe, restore the notebook from before the refactor so I can compare

### 4. Querying: `scribe, what/when/show me...`

When the user asks questions about past work:

**Time-based queries** — read the relevant day files directly:

- "scribe, what did we do today?" → read `.scribe/YYYY-MM-DD.md` (today)
- "scribe, show me yesterday's work" → read yesterday's file
- "scribe, summarize last week" → read the last 7 day files

For multi-day queries, read efficiently in one command:
```bash
# Last 7 days (adjust dates as needed)
cat .scribe/2026-01-{18..24}.md

# Or dynamically
ls .scribe/*.md | tail -7 | xargs cat

# Just recent entries from each file
tail -50 .scribe/2026-01-{18..24}.md
```

**Topic-based queries** — grep first, then read matching files:

- "scribe, what did we try for the null problem?" → `grep -l "null" .scribe/*.md`, then read matches
- "scribe, when did we last touch the ETL?" → `grep -l "ETL" .scribe/*.md`, then read matches

**Thread queries** — find entries that reference a given entry:

- "scribe, what entries build on the feature engineering work?" → find the entry's ID, then `grep -l "{entry-id}" .scribe/*.md` to find entries that reference it in their **Related** section

**Asset queries** — use the list command, then search logs if needed:

- "scribe, show me snapshots of the notebook" → `python assets.py list notebook`
- "scribe, what version of clustering.ipynb worked?" → search logs for "clustering" + "worked"

**Process:**

1. Determine if time-based or topic-based
2. For time-based: read the relevant day files directly
3. For topic-based: grep for keywords, then read only matching files
4. Synthesize an answer from the entries

**Example questions:**

- "scribe, what did we do today?"
- "scribe, what's still unresolved?"
- "scribe, what did we try for the null value problem?"
- "scribe, when did we last touch the ETL pipeline?"
- "scribe, show me last week's work"
- "scribe, what snapshots do we have of the notebook?"

## Validation

After every entry (logging or archiving), run validation to catch any issues:

```bash
python validate.py
```

Validation checks:
- Every entry has an ID
- Entry ID format is valid
- Archived files referenced in entries actually exist
- Related references point to valid entry IDs
- No orphaned assets (files in `assets/` not referenced by any entry)

If validation fails, fix the issue before continuing. Use `edit-latest` commands to fix or remove broken entries.

## Initialization

On first invocation, if `.scribe/` doesn't exist, create it automatically:

```bash
mkdir -p .scribe/assets
```

Add `.scribe/` to the parent repo's `.gitignore`.

This happens automatically when the user first addresses the scribe — no manual setup required.

**First entry:** If starting fresh, capture what you're about to do. If joining an existing project, capture where things stand. If asked, Claude can explore the project (README, git log, file structure) to help draft this entry.

## Limitations

- **Single session:** Not designed for concurrent access from multiple Claude sessions. If two sessions write simultaneously, race conditions may occur.
- **Project scale:** Best suited for weeks-to-months of exploratory work, not permanent archives. For long-term projects (1+ year), consider periodically archiving old logs elsewhere.
- **No atomic writes:** Interrupted writes may leave partial state. Validation will catch inconsistencies.

## Principles

- **Be a narrator, not a stenographer.** Write prose that tells the story, not raw tool dumps.
- **Capture the why.** Not just what happened, but why it was tried, why it failed.
- **Stay concise.** Each entry should be scannable. Details belong in the code.
- **Preserve dead ends.** Failed approaches prevent repeating mistakes.
- **Track open threads.** Note unresolved questions for later.
- **Archive at meaningful moments.** Snapshot when something works, before a risky change, or when the user says to.
