#!/usr/bin/env python3
"""
Viz Runner - Artifact management for the viz skill.

Usage:
    python viz_runner.py [--id NAME] < script_content
    python viz_runner.py [--id NAME] --file /path/to/script.py
    echo "script content" | python viz_runner.py --id my_plot

The runner:
1. Creates /tmp/viz/ if it doesn't exist
2. Ensures ID uniqueness (appends _2, _3, etc. if needed)
3. Injects plt.savefig() before any plt.show() call
4. Writes the modified script to /tmp/viz/<id>.py
5. Executes the script
6. Prints the final ID and paths to stdout
"""

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

VIZ_DIR = Path("/tmp/viz")


def ensure_viz_dir():
    """Create /tmp/viz/ if it doesn't exist."""
    VIZ_DIR.mkdir(parents=True, exist_ok=True)


def get_unique_id(suggested_id: str | None) -> str:
    """
    Generate a unique ID for the visualization.

    If suggested_id is provided, check if it exists and append _2, _3, etc.
    If no suggested_id, generate a timestamp-based ID.
    """
    if suggested_id is None:
        # Generate timestamp-based ID
        base_id = datetime.now().strftime("viz_%Y%m%d_%H%M%S")
    else:
        base_id = suggested_id

    # Check if the base ID is available
    if not (VIZ_DIR / f"{base_id}.py").exists():
        return base_id

    # Find the next available suffix
    counter = 2
    while (VIZ_DIR / f"{base_id}_{counter}.py").exists():
        counter += 1

    return f"{base_id}_{counter}"


def inject_savefig(script: str, png_path: str) -> str:
    """
    Inject plt.savefig() before plt.show() calls.

    Handles various patterns:
    - plt.show()
    - pyplot.show()
    - fig.show() (less common but possible)
    """
    savefig_line = f"plt.savefig('{png_path}', dpi=150, bbox_inches='tight')"

    # Pattern to match plt.show() or pyplot.show() with optional whitespace
    # We insert savefig on the line before show()
    pattern = r'^(\s*)(plt\.show\(\)|pyplot\.show\(\))'

    def replacement(match):
        indent = match.group(1)
        show_call = match.group(2)
        return f"{indent}{savefig_line}\n{indent}{show_call}"

    modified = re.sub(pattern, replacement, script, flags=re.MULTILINE)

    # If no plt.show() was found, append savefig at the end
    if modified == script:
        # Check if matplotlib is imported
        if 'matplotlib' in script or 'plt' in script:
            modified = script.rstrip() + f"\n\n# Auto-injected by viz_runner\n{savefig_line}\n"

    return modified


def run_script_background(script_path: Path, png_path: Path) -> tuple[bool, int, str]:
    """
    Execute the script in background and wait for PNG to be created.
    Returns (success, pid, message).

    The script runs as a detached process so plt.show() doesn't block.
    Since savefig() is injected BEFORE plt.show(), the PNG gets created
    immediately while the interactive window stays open.
    """
    try:
        # Start script as detached background process
        process = subprocess.Popen(
            [sys.executable, str(script_path)],
            start_new_session=True,  # Detach from terminal
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            cwd=str(VIZ_DIR),
        )

        # Poll for PNG (savefig happens before plt.show)
        max_wait = 3.0
        poll_interval = 0.1
        waited = 0.0

        while waited < max_wait:
            if png_path.exists():
                return True, process.pid, "Plot window opened"
            time.sleep(poll_interval)
            waited += poll_interval

            # Check if process failed early
            if process.poll() is not None:
                stderr = process.stderr.read().decode() if process.stderr else ""
                return False, 0, f"Script failed: {stderr}"

        # Timeout waiting for PNG
        return False, process.pid, "Timeout waiting for PNG (script may still be running)"

    except Exception as e:
        return False, 0, f"Error: {e}"


def main():
    parser = argparse.ArgumentParser(description="Viz Runner - artifact management for viz skill")
    parser.add_argument("--id", dest="suggested_id", help="Suggested ID for the visualization")
    parser.add_argument("--desc", dest="description", help="Description of the visualization")
    parser.add_argument("--file", dest="script_file", help="Path to script file (alternative to stdin)")
    parser.add_argument("--clean", action="store_true", help="Remove all files from /tmp/viz/")
    parser.add_argument("--list", action="store_true", help="List all visualizations")
    args = parser.parse_args()

    # Handle clean action early
    if args.clean:
        ensure_viz_dir()
        count = 0
        for f in VIZ_DIR.iterdir():
            if f.is_file():
                f.unlink()
                count += 1
        print(f"Cleaned {count} files from {VIZ_DIR}")
        sys.exit(0)

    # Handle list action
    if args.list:
        ensure_viz_dir()
        json_files = sorted(VIZ_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        if not json_files:
            print("No visualizations found")
            sys.exit(0)

        # Collect metadata
        rows = []
        for jf in json_files:
            meta = json.loads(jf.read_text())
            rows.append({
                "id": meta.get("id", jf.stem),
                "desc": meta.get("desc") or "-",
                "created": meta.get("created", "")[:16].replace("T", " "),
            })

        # Calculate column widths
        id_width = max(len("ID"), max(len(r["id"]) for r in rows))
        desc_width = max(len("Description"), max(len(r["desc"]) for r in rows))

        # Print table
        header = f"{'ID':<{id_width}}  {'Description':<{desc_width}}  Created"
        print(header)
        print(f"{'-' * id_width}  {'-' * desc_width}  {'-' * 16}")
        for r in rows:
            print(f"{r['id']:<{id_width}}  {r['desc']:<{desc_width}}  {r['created']}")
        sys.exit(0)

    # Ensure output directory exists
    ensure_viz_dir()

    # Read script content
    if args.script_file:
        try:
            with open(args.script_file, 'r') as f:
                script_content = f.read()
        except Exception as e:
            print(f"error: Could not read script file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Read from stdin
        if sys.stdin.isatty():
            print("error: No script provided. Pipe script content or use --file", file=sys.stderr)
            sys.exit(1)
        script_content = sys.stdin.read()

    if not script_content.strip():
        print("error: Empty script provided", file=sys.stderr)
        sys.exit(1)

    # Get unique ID
    final_id = get_unique_id(args.suggested_id)

    # Determine paths
    script_path = VIZ_DIR / f"{final_id}.py"
    png_path = VIZ_DIR / f"{final_id}.png"

    # Inject savefig
    modified_script = inject_savefig(script_content, str(png_path))

    # Write script
    script_path.write_text(modified_script)

    # Execute script in background (non-blocking)
    success, pid, message = run_script_background(script_path, png_path)

    # Write sidecar JSON metadata file
    json_path = VIZ_DIR / f"{final_id}.json"
    metadata = {
        "id": final_id,
        "desc": args.description,
        "png": str(png_path),
        "script": str(script_path),
        "created": datetime.now().isoformat(timespec="seconds"),
        "pid": pid,
    }
    json_path.write_text(json.dumps(metadata, indent=2))

    # Print human-readable output
    print(f"Plot: {final_id}")
    if args.description:
        print(f'  "{args.description}"')
    print(f"  png: {png_path}")

    if not success:
        print(f"  error: {message}")

    # Check if PNG was actually created
    if success and not png_path.exists():
        print("  warning: Script executed but PNG was not created")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
