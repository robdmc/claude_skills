# Test: Archive Files

## Purpose

Verify scribe correctly archives files to `.scribe/assets/` and links them in entries.

## Setup

1. cd to `tests/workspace/`
2. Run 01_init test OR manually create `.scribe/assets/`
3. Copy fixture file: `cp ../fixtures/sample.py ./analysis.py`

## Steps

1. Say: "scribe, save analysis.py - this is the working version"
2. When Claude proposes an entry with archive, confirm it

## Verify

- [ ] New entry appears in today's log
- [ ] Entry has **Archived:** section
- [ ] Asset file exists in `.scribe/assets/` with format: `YYYY-MM-DD-HH-MM-analysis.py`
- [ ] Asset filename matches what's in entry's markdown link
- [ ] The archived file content matches the original
- [ ] Run: `python ../../code/scripts/validate.py` - should pass

## Multi-file Test (Optional)

1. Copy another fixture: `cp ../fixtures/sample.md ./notes.md`
2. Say: "scribe, snapshot both analysis.py and notes.md"
3. Verify both files are archived with the same entry ID prefix

## Cleanup

```bash
python ../cleanup.py
```
