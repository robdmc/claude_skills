# Test: Basic Logging

## Purpose

Verify scribe creates well-formatted entries and appends to existing log files.

## Setup

1. cd to `tests/workspace/`
2. Run 01_init test first OR manually create `.scribe/` structure
3. Wait at least one minute after any previous entry (to avoid collision)

## Steps

1. Create a test file: `echo "test content" > analysis.py`
2. Say: "scribe, log this - I created an analysis file to start working"
3. When Claude proposes an entry, confirm it
4. Wait at least one minute
5. Say: "scribe, log this - made progress on the analysis"
6. Confirm the second entry

## Verify

- [ ] Today's log file has two entries
- [ ] Each entry has unique ID comment
- [ ] Entries appear in chronological order (newer at bottom)
- [ ] Each entry has H2 title, narrative, and Status
- [ ] File separation exists between entries (blank lines)
- [ ] Run: `python ../../code/scripts/validate.py` - should pass

## Cleanup

```bash
python ../cleanup.py
```
