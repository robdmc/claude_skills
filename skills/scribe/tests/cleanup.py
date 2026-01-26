#!/usr/bin/env python3
"""Remove all scribe test artifacts."""
import shutil
from pathlib import Path


def cleanup():
    tests_dir = Path(__file__).parent
    workspace = tests_dir / "workspace"

    # Remove workspace entirely
    if workspace.exists():
        shutil.rmtree(workspace)
        print(f"Removed: {workspace}")

    # Recreate empty workspace
    workspace.mkdir()
    (workspace / ".gitkeep").touch()
    print(f"Created fresh: {workspace}")


if __name__ == "__main__":
    cleanup()
    print("Cleanup complete.")
