#!/usr/bin/env python3
"""Validate scribe entries for consistency.

Requires Python 3.9+ (uses built-in generic types).
"""

import re
import sys
from pathlib import Path

from common import ENTRY_ID_PATTERN, find_scribe_dir


def extract_entries(log_file: Path) -> list[dict]:
    """Extract entries from a daily log file."""
    content = log_file.read_text()
    entries = []
    
    # Pattern for entry headers: ## HH:MM — Title
    header_pattern = re.compile(r"^## (\d{2}:\d{2}) — (.+)$", re.MULTILINE)
    # Pattern for entry ID: <!-- id: YYYY-MM-DD-HH-MM -->
    id_pattern = re.compile(r"<!-- id: ([\d-]+) -->")
    # Pattern for archived files: [`filename`](assets/filename)
    archive_pattern = re.compile(r"\[`([^`]+)`\]\(assets/([^)]+)\)")
    # Pattern for Related section
    related_section_pattern = re.compile(r"\*\*Related:\*\*(.+?)(?=\n\n|\n\*\*|\n---|\Z)", re.DOTALL)
    # Pattern for entry IDs within Related section
    related_id_pattern = re.compile(r"(\d{4}-\d{2}-\d{2}-\d{2}-\d{2}(?:-\d{2,})?)")
    
    # Split by entry headers
    parts = header_pattern.split(content)
    
    # parts[0] is content before first entry (usually just "# YYYY-MM-DD\n---")
    # then triplets of (time, title, body)
    for i in range(1, len(parts), 3):
        if i + 2 >= len(parts):
            break
        time = parts[i]
        title = parts[i + 1]
        body = parts[i + 2] if i + 2 < len(parts) else ""
        
        # Extract ID
        id_match = id_pattern.search(body)
        entry_id = id_match.group(1) if id_match else None
        
        # Extract archived file references
        archived = archive_pattern.findall(body)
        
        # Extract Related entry IDs (only from Related section)
        related = []
        related_section_match = related_section_pattern.search(body)
        if related_section_match:
            related_text = related_section_match.group(1)
            related = related_id_pattern.findall(related_text)
        
        entries.append({
            "file": log_file.name,
            "time": time,
            "title": title,
            "id": entry_id,
            "archived": archived,  # list of (display_name, asset_path) tuples
            "related": related,    # list of entry IDs referenced in Related section
        })
    
    return entries


def validate(scribe_dir: Path) -> tuple[list[str], int]:
    """Validate all entries and return (errors, entry_count)."""
    errors = []
    assets_dir = scribe_dir / "assets"
    
    # Find all log files (YYYY-MM-DD.md pattern)
    log_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")
    log_files = [f for f in scribe_dir.iterdir() if log_pattern.match(f.name)]
    
    all_entries = []
    
    for log_file in sorted(log_files):
        entries = extract_entries(log_file)
        all_entries.extend(entries)
        
        for entry in entries:
            # Check: entry has ID
            if not entry["id"]:
                errors.append(
                    f"✗ {log_file.name} [{entry['time']}] \"{entry['title']}\" — missing entry ID"
                )
            # Check: entry ID format is valid
            elif not ENTRY_ID_PATTERN.match(entry["id"]):
                errors.append(
                    f"✗ {log_file.name} [{entry['time']}] — invalid entry ID format: {entry['id']}"
                )
            
            # Check: archived files exist
            for display_name, asset_path in entry["archived"]:
                asset_file = assets_dir / asset_path
                if not asset_file.exists():
                    errors.append(
                        f"✗ {log_file.name} [{entry['time']}] — references {asset_path} but file not found"
                    )
    
    # Collect all valid entry IDs for Related validation
    all_entry_ids = {entry["id"] for entry in all_entries if entry["id"]}
    
    # Check: Related references point to valid entries
    for entry in all_entries:
        for related_id in entry.get("related", []):
            if related_id not in all_entry_ids:
                errors.append(
                    f"✗ {entry['file']} [{entry['time']}] — Related references {related_id} but entry not found"
                )
    
    # Check for orphaned assets (assets with no corresponding entry)
    if assets_dir.exists():
        referenced_assets = set()
        for entry in all_entries:
            for _, asset_path in entry["archived"]:
                referenced_assets.add(asset_path)
        
        for asset_file in assets_dir.iterdir():
            if asset_file.name not in referenced_assets:
                errors.append(
                    f"✗ Orphaned asset: {asset_file.name} — no entry references it"
                )
    
    return errors, len(all_entries)


def main():
    scribe_dir = find_scribe_dir()
    
    if not scribe_dir or not scribe_dir.exists():
        print("Error: .scribe directory not found", file=sys.stderr)
        sys.exit(1)
    
    errors, entry_count = validate(scribe_dir)
    
    if errors:
        for error in errors:
            print(error)
        sys.exit(1)
    else:
        print(f"✓ {entry_count} entries validated")
        sys.exit(0)


if __name__ == "__main__":
    main()
