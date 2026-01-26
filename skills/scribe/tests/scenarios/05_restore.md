# Test: Restore Files

## Purpose

Verify scribe correctly restores archived files with underscore prefix.

## Setup

1. cd to `tests/workspace/`
2. Run 04_archive test first (need an archived file)
3. OR manually set up:
   - Create `.scribe/assets/`
   - Copy a file to assets with proper naming: `cp ../fixtures/sample.py .scribe/assets/2026-01-01-12-00-analysis.py`
   - Create a log entry referencing it

## Steps

1. Say: "scribe, restore analysis.py"
2. Claude should find the archived version and restore it

## Verify

- [ ] Restored file appears with underscore prefix: `_YYYY-MM-DD-HH-MM-analysis.py`
- [ ] File is restored to workspace directory (or original path if from deep directory)
- [ ] Restored file content matches the archived version
- [ ] Original file (if present) is untouched
- [ ] Run: `python ../../code/scripts/validate.py` - should pass

## List Assets Test

1. Say: "scribe, what snapshots do we have?"
2. Verify Claude lists available assets

## Restore Conflict Test

1. Run restore again on same file
2. Should fail with "already exists" error
3. Remove the restored file: `rm _*-analysis.py`
4. Restore should work again

## Cleanup

```bash
python ../cleanup.py
```
