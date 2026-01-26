# Scribe Skill Test Framework

Manual test scenarios for exercising the scribe skill.

## Structure

```
tests/
├── README.md              # This file
├── cleanup.py             # Remove all test artifacts
├── workspace/             # Isolated test environment
├── scenarios/             # Test scenario files
│   ├── 01_init.md
│   ├── 02_basic_logging.md
│   ├── 03_collision.md
│   ├── 04_archive.md
│   ├── 05_restore.md
│   ├── 06_validation.md
│   ├── 07_edit_latest.md
│   └── 08_related.md
└── fixtures/              # Sample files for tests
    ├── sample.py
    └── sample.md
```

## Running Tests

1. Open a scenario file (e.g., `scenarios/01_init.md`)
2. Follow the Setup steps
3. Execute the Steps (interact with Claude using the scribe skill)
4. Check the Verify items
5. Run cleanup: `python cleanup.py`

## Test Order

Tests are numbered for a suggested order, but each test can run independently after cleanup.

| Scenario | What It Tests |
|----------|---------------|
| 01_init | Directory creation, first entry |
| 02_basic_logging | Entry writing, format, appending |
| 03_collision | ID collision handling (same minute) |
| 04_archive | Save files to assets |
| 05_restore | Get files back, underscore prefix |
| 06_validation | Catch errors, orphans |
| 07_edit_latest | Show, delete, replace, unarchive |
| 08_related | Entry linking |

## Cleanup

Always run cleanup between tests:

```bash
python cleanup.py
```

This removes all artifacts from `workspace/` and creates a fresh empty directory.
