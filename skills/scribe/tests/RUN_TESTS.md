# Running Scribe Skill Tests

This document tells you how to exercise the scribe skill through manual test scenarios.

## Project Structure

```
scribe/
├── code/
│   ├── SKILL.md              # Skill definition (read this first)
│   └── scripts/
│       ├── validate.py       # Validates .scribe/ integrity
│       ├── entry.py          # Entry management
│       └── assets.py         # Asset management
└── tests/
    ├── RUN_TESTS.md          # This file
    ├── cleanup.py            # Resets workspace to empty state
    ├── workspace/            # Isolated directory where tests run
    ├── scenarios/            # Test scenario files
    └── fixtures/             # Sample files for archive tests
```

## Before You Start

1. **Read the skill definition:** `code/SKILL.md`

   This tells you how the scribe skill works - what commands it responds to, what files it creates, and how to interact with it.

2. **Understand the workspace:**

   All tests run inside `tests/workspace/`. This is where `.scribe/` directories get created. It's isolated so tests don't affect real projects.

## Running a Test

### 1. Reset the workspace

```bash
cd tests
python cleanup.py
```

This removes everything in `workspace/` and creates a fresh empty directory.

### 2. Enter the workspace

```bash
cd workspace
```

### 3. Open a scenario file

Each scenario in `scenarios/` has:
- **Purpose** - What the test verifies
- **Setup** - Preparation steps (copy files, create directories)
- **Steps** - Phrases to say to invoke the scribe skill
- **Verify** - Checklist of things to confirm
- **Cleanup** - How to reset (usually just `python ../cleanup.py`)

### 4. Execute the Steps

The Steps section contains phrases like:
- "hey scribe, I'm starting an analysis"
- "scribe, log this"
- "scribe, save analysis.py"

Say these phrases in the conversation. The scribe skill will respond by proposing entries, archiving files, etc.

### 5. Check the Verify items

After completing the steps, confirm each checkbox item. Common verifications:
- Check that files/directories exist
- Check file contents match expected format
- Run `python ../../code/scripts/validate.py` to verify integrity

## Test Scenarios

Run in order. Each is independent after cleanup.

| Scenario | What It Tests |
|----------|---------------|
| `01_init.md` | Creating `.scribe/` directory, first log entry |
| `02_basic_logging.md` | Entry format, multiple entries, appending |
| `03_collision.md` | Two entries in same minute get unique IDs |
| `04_archive.md` | Saving files to `.scribe/assets/` |
| `05_restore.md` | Retrieving archived files with `_` prefix |
| `06_validation.md` | Detecting missing assets and orphans |
| `07_edit_latest.md` | Show, delete, replace, unarchive commands |
| `08_related.md` | Linking entries with **Related:** section |

## Running All Tests

For each scenario (01 through 08):

1. `cd tests && python cleanup.py`
2. `cd workspace`
3. Read `scenarios/XX_name.md`
4. Follow Setup steps
5. Execute Steps (say the phrases, confirm proposed entries)
6. Check all Verify items
7. Record pass/fail

## Quick Reference

| Task | Command |
|------|---------|
| Reset workspace | `python tests/cleanup.py` |
| Validate .scribe/ | `python code/scripts/validate.py` |
| Copy fixture | `cp tests/fixtures/sample.py tests/workspace/` |
