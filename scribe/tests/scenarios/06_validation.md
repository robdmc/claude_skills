# Test: Validation

## Purpose

Verify the validation script catches errors and orphaned assets.

## Setup

1. cd to `tests/workspace/`
2. Create `.scribe/` and `.scribe/assets/` directories
3. Create a log file with an entry

## Steps

### Test 1: Missing Asset Reference

1. Create a log entry that references a non-existent asset:
   ```bash
   mkdir -p .scribe/assets
   cat > .scribe/2026-01-01.md << 'EOF'
   # 2026-01-01

   <!-- id: 2026-01-01-12-00 -->
   ## Test Entry

   Testing validation.

   **Archived:**
   - `test.py` → [`2026-01-01-12-00-test.py`](assets/2026-01-01-12-00-test.py)

   **Status:** Testing
   EOF
   ```

2. Run validation: `python ../../code/scripts/validate.py`

## Verify (Test 1)

- [ ] Validation reports missing asset error
- [ ] Error message identifies which asset is missing
- [ ] Exit code is non-zero

### Test 2: Orphaned Asset

1. Reset: `python ../cleanup.py`
2. Create an orphaned asset:
   ```bash
   mkdir -p .scribe/assets
   echo "orphan" > .scribe/assets/2026-01-01-12-00-orphan.py
   cat > .scribe/2026-01-01.md << 'EOF'
   # 2026-01-01

   <!-- id: 2026-01-01-12-00 -->
   ## Test Entry

   Testing validation.

   **Status:** Testing
   EOF
   ```

3. Run validation: `python ../../code/scripts/validate.py`

## Verify (Test 2)

- [ ] Validation reports orphaned asset warning
- [ ] Warning identifies the orphaned file

### Test 3: Valid State

1. Reset and run 04_archive test to create valid state
2. Run validation: `python ../../code/scripts/validate.py`

## Verify (Test 3)

- [ ] Validation passes with no errors
- [ ] Exit code is zero

## Cleanup

```bash
python ../cleanup.py
```
