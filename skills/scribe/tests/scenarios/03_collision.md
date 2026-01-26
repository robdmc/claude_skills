# Test: ID Collision Handling

## Purpose

Verify scribe handles multiple entries in the same minute by appending sequence numbers.

## Setup

1. cd to `tests/workspace/`
2. Ensure `.scribe/` exists (run 01_init or create manually)

## Steps

1. Say: "scribe, quick log: first entry for collision test"
2. Immediately (within same minute) say: "scribe, quick log: second entry same minute"
3. If possible, immediately say: "scribe, quick log: third entry same minute"

## Verify

- [ ] First entry has ID: `YYYY-MM-DD-HH-MM`
- [ ] Second entry has ID: `YYYY-MM-DD-HH-MM-02`
- [ ] Third entry (if created) has ID: `YYYY-MM-DD-HH-MM-03`
- [ ] All entries are valid and complete
- [ ] Run: `python ../../code/scripts/validate.py` - should pass

## Notes

- Quick log bypasses the propose/confirm cycle, making it easier to create multiple entries rapidly
- The collision detection happens in `entry.py` when generating the ID

## Cleanup

```bash
python ../cleanup.py
```
