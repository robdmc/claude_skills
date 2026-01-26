# Test: Initialize Scribe

## Purpose

Verify scribe correctly initializes `.scribe/` directory structure and creates the first entry.

## Setup

1. cd to `tests/workspace/` (create if needed)
2. Ensure no `.scribe/` directory exists: `rm -rf .scribe`

## Steps

1. Say: "hey scribe, I'm starting an analysis to test the skill"
2. When Claude proposes an entry, confirm it

## Verify

- [ ] `.scribe/` directory was created
- [ ] `.scribe/assets/` subdirectory exists
- [ ] A log file exists: `.scribe/YYYY-MM-DD.md`
- [ ] Log file has header: `# YYYY-MM-DD`
- [ ] Entry has valid ID comment: `<!-- id: YYYY-MM-DD-HH-MM -->`
- [ ] Entry has title (H2)
- [ ] Entry has narrative text
- [ ] Entry has **Status:** line

## Cleanup

```bash
python ../cleanup.py
```
