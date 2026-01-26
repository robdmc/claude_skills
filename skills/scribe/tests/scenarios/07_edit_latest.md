# Test: Edit Latest Entry

## Purpose

Verify the edit-latest commands: show, delete, replace, unarchive.

## Setup

1. cd to `tests/workspace/`
2. Run 04_archive test first (creates entry with archived file)

## Steps

### Test 1: Show Latest

1. Say: "scribe, show me what you just logged"
2. Claude should run `entry.py edit-latest show`

## Verify (Test 1)

- [ ] Entry content is displayed
- [ ] Shows the ID, title, narrative, and archived section

### Test 2: Replace Content

1. Say: "scribe, update the last entry - change the status to 'Completed'"
2. Claude should run `entry.py edit-latest replace` with updated content

## Verify (Test 2)

- [ ] Entry content is updated
- [ ] Entry ID remains the same
- [ ] Archived files are still linked
- [ ] Run: `python ../../code/scripts/validate.py` - should pass

### Test 3: Unarchive

1. Say: "scribe, remove the archived files from the last entry but keep the entry"
2. Claude should run `entry.py edit-latest unarchive`

## Verify (Test 3)

- [ ] Asset files are deleted from `.scribe/assets/`
- [ ] Entry still exists (may still have Archived section text)
- [ ] Run: `python ../../code/scripts/validate.py` - check behavior

### Test 4: Delete Entry

1. First create a new entry: "scribe, quick log: test entry for deletion"
2. Say: "scribe, delete that last entry"
3. Claude should run `entry.py edit-latest delete`

## Verify (Test 4)

- [ ] Entry is removed from log file
- [ ] Any associated assets are also removed
- [ ] Run: `python ../../code/scripts/validate.py` - should pass

## Cleanup

```bash
python ../cleanup.py
```
