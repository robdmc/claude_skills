# Test: Related Entries

## Purpose

Verify scribe correctly links related entries using the **Related:** section.

## Setup

1. cd to `tests/workspace/`
2. Ensure `.scribe/` exists (run 01_init or create manually)

## Steps

### Test 1: Simple Follow-up

1. Say: "scribe, log this - starting investigation into data quality issues"
2. Confirm the entry, note the entry ID
3. Wait at least one minute
4. Say: "scribe, add to the last entry - found that nulls are the main problem"
5. Confirm the entry

## Verify (Test 1)

- [ ] Second entry has **Related:** section
- [ ] Related section links to first entry's ID
- [ ] Link format: `[Title](YYYY-MM-DD.md#YYYY-MM-DD-HH-MM)`
- [ ] Run: `python ../../code/scripts/validate.py` - should pass

### Test 2: Multiple Related

1. Create a third entry: "scribe, the null issue connects to both the data quality investigation and a timezone problem we found"
2. When proposing, Claude should suggest linking to multiple entries

## Verify (Test 2)

- [ ] Entry has **Related:** section with multiple links
- [ ] Each link has the entry title and proper ID reference

### Test 3: Closing a Thread

1. Say: "scribe, the null investigation is complete - it was caused by the ETL script"
2. Confirm entry, should reference the investigation entries

## Verify (Test 3)

- [ ] Entry narrative indicates resolution
- [ ] **Related:** links back to relevant investigation entries
- [ ] Status indicates completion

### Test 4: Query Related

1. Say: "scribe, show me everything related to the null investigation"
2. Claude should search logs and find the thread

## Verify (Test 4)

- [ ] Claude finds and summarizes the related entries
- [ ] Thread is traceable through Related links

## Cleanup

```bash
python ../cleanup.py
```
