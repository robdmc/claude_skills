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
import re
import subprocess
import sys
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


def run_script(script_path: Path) -> tuple[bool, str]:
    """
    Execute the script and return (success, output).
    """
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout
            cwd=str(VIZ_DIR),
        )

        output = result.stdout
        if result.stderr:
            output += "\n" + result.stderr

        return result.returncode == 0, output.strip()
    except subprocess.TimeoutExpired:
        return False, "Error: Script execution timed out (120s limit)"
    except Exception as e:
        return False, f"Error executing script: {e}"


def main():
    parser = argparse.ArgumentParser(description="Viz Runner - artifact management for viz skill")
    parser.add_argument("--id", dest="suggested_id", help="Suggested ID for the visualization")
    parser.add_argument("--file", dest="script_file", help="Path to script file (alternative to stdin)")
    args = parser.parse_args()

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

    # Execute script
    success, output = run_script(script_path)

    # Print results
    print(f"id: {final_id}")
    print(f"script: {script_path}")
    print(f"png: {png_path}")
    print(f"success: {success}")

    if output:
        print(f"output: {output}")

    # Check if PNG was actually created
    if success and not png_path.exists():
        print("warning: Script executed but PNG was not created")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
