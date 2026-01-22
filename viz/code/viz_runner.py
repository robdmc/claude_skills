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
import ast
import json
import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

VIZ_DIR = Path("/tmp/viz")


# ============================================================================
# Marimo Notebook Support
# ============================================================================


@dataclass
class MarimoCell:
    """Represents a single cell in a marimo notebook."""

    name: str  # Function name (e.g., "_" or "my_cell")
    refs: list[str]  # Variables this cell reads (from function params)
    defs: list[str]  # Variables this cell defines (from return tuple)
    code: str  # Full cell code including decorator and function def
    start_line: int  # Line number where cell starts (1-indexed)
    end_line: int  # Line number where cell ends (1-indexed)


@dataclass
class MarimoFunction:
    """Represents an @app.function decorated function."""

    name: str
    code: str
    start_line: int
    end_line: int


@dataclass
class MarimoClass:
    """Represents a class definition in the notebook."""

    name: str
    code: str
    start_line: int
    end_line: int


@dataclass
class ParsedNotebook:
    """Parsed structure of a marimo notebook."""

    preamble: str  # Everything before app.setup (imports marimo, app = ...)
    setup_code: str  # Content of app.setup block
    functions: list[MarimoFunction] = field(default_factory=list)
    classes: list[MarimoClass] = field(default_factory=list)
    cells: list[MarimoCell] = field(default_factory=list)
    main_block: str = ""  # The if __name__ == "__main__" block


def parse_marimo_notebook(notebook_path: Path) -> ParsedNotebook:
    """
    Parse a marimo notebook using AST and extract cell structure.

    Extracts:
    - Preamble (import marimo, app = marimo.App(...))
    - Setup block (with app.setup:)
    - @app.function definitions
    - Class definitions
    - @app.cell definitions with refs/defs
    - Main block
    """
    with open(notebook_path) as f:
        source = f.read()
        source_lines = source.splitlines(keepends=True)

    tree = ast.parse(source)

    result = ParsedNotebook(preamble="", setup_code="")

    # Track positions
    setup_start = None
    setup_end = None
    main_start = None

    for node in ast.iter_child_nodes(tree):
        # Find import marimo and app = marimo.App(...)
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            # Part of preamble
            pass

        # Find with app.setup: block
        elif isinstance(node, ast.With):
            for item in node.items:
                ctx = item.context_expr
                if (
                    isinstance(ctx, ast.Attribute)
                    and isinstance(ctx.value, ast.Name)
                    and ctx.value.id == "app"
                    and ctx.attr == "setup"
                ):
                    setup_start = node.lineno
                    setup_end = node.end_lineno
                    # Extract the body of the with block
                    body_start = node.body[0].lineno if node.body else setup_start + 1
                    body_end = setup_end
                    setup_lines = source_lines[body_start - 1 : body_end]
                    result.setup_code = "".join(setup_lines)

        # Find @app.cell and @app.function decorated functions
        elif isinstance(node, ast.FunctionDef):
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Attribute):
                    if (
                        isinstance(decorator.value, ast.Name)
                        and decorator.value.id == "app"
                    ):
                        if decorator.attr == "cell":
                            cell = _parse_cell(node, source_lines)
                            result.cells.append(cell)
                        elif decorator.attr == "function":
                            func = _parse_function(node, source_lines)
                            result.functions.append(func)

        # Find class definitions
        elif isinstance(node, ast.ClassDef):
            cls = _parse_class(node, source_lines)
            result.classes.append(cls)

        # Find if __name__ == "__main__":
        elif isinstance(node, ast.If):
            if _is_main_block(node):
                main_start = node.lineno
                result.main_block = "".join(source_lines[main_start - 1 :])

    # Extract preamble (everything before setup or first cell)
    if setup_start:
        result.preamble = "".join(source_lines[: setup_start - 1])
    elif result.cells:
        first_cell_line = result.cells[0].start_line
        result.preamble = "".join(source_lines[: first_cell_line - 1])

    return result


def _parse_cell(node: ast.FunctionDef, source_lines: list[str]) -> MarimoCell:
    """Parse an @app.cell decorated function into a MarimoCell."""
    # Get refs from function parameters
    refs = []
    for arg in node.args.args:
        if arg.arg != "_":  # Skip underscore params
            refs.append(arg.arg)

    # Get defs from return statement
    defs = []
    for stmt in ast.walk(node):
        if isinstance(stmt, ast.Return) and stmt.value:
            if isinstance(stmt.value, ast.Tuple):
                for elt in stmt.value.elts:
                    if isinstance(elt, ast.Name):
                        defs.append(elt.id)

    # Extract full code
    start_line = node.lineno
    # Account for decorators
    for decorator in node.decorator_list:
        start_line = min(start_line, decorator.lineno)
    end_line = node.end_lineno or node.lineno

    code = "".join(source_lines[start_line - 1 : end_line])

    return MarimoCell(
        name=node.name,
        refs=refs,
        defs=defs,
        code=code,
        start_line=start_line,
        end_line=end_line,
    )


def _parse_function(node: ast.FunctionDef, source_lines: list[str]) -> MarimoFunction:
    """Parse an @app.function decorated function."""
    start_line = node.lineno
    for decorator in node.decorator_list:
        start_line = min(start_line, decorator.lineno)
    end_line = node.end_lineno or node.lineno

    code = "".join(source_lines[start_line - 1 : end_line])

    return MarimoFunction(
        name=node.name, code=code, start_line=start_line, end_line=end_line
    )


def _parse_class(node: ast.ClassDef, source_lines: list[str]) -> MarimoClass:
    """Parse a class definition."""
    start_line = node.lineno
    for decorator in node.decorator_list:
        start_line = min(start_line, decorator.lineno)
    end_line = node.end_lineno or node.lineno

    code = "".join(source_lines[start_line - 1 : end_line])

    return MarimoClass(
        name=node.name, code=code, start_line=start_line, end_line=end_line
    )


def _is_main_block(node: ast.If) -> bool:
    """Check if this is an if __name__ == '__main__': block."""
    test = node.test
    if isinstance(test, ast.Compare):
        if (
            isinstance(test.left, ast.Name)
            and test.left.id == "__name__"
            and len(test.ops) == 1
            and isinstance(test.ops[0], ast.Eq)
            and len(test.comparators) == 1
            and isinstance(test.comparators[0], ast.Constant)
            and test.comparators[0].value == "__main__"
        ):
            return True
    return False


def get_required_cells(
    parsed: ParsedNotebook, target_vars: list[str]
) -> tuple[list[int], set[str]]:
    """
    Given target variables, return indices of all cells needed.

    Works backwards from targets through the dependency graph.
    Also returns the set of @app.function names that are needed.

    Returns:
        (cell_indices, function_names): List of cell indices and set of function names
    """
    # Build a map of variable -> cell index that defines it
    var_to_cell: dict[str, int] = {}
    for i, cell in enumerate(parsed.cells):
        for var in cell.defs:
            var_to_cell[var] = i

    # Build set of all function names
    function_names = {f.name for f in parsed.functions}

    # Traverse backwards from target vars
    required_indices: set[int] = set()
    required_functions: set[str] = set()
    queue = list(target_vars)
    visited_vars: set[str] = set()

    while queue:
        var = queue.pop()
        if var in visited_vars:
            continue
        visited_vars.add(var)

        # Check if this var is defined by a cell
        if var in var_to_cell:
            cell_idx = var_to_cell[var]
            required_indices.add(cell_idx)
            # Add this cell's refs to the queue
            cell = parsed.cells[cell_idx]
            for ref in cell.refs:
                if ref not in visited_vars:
                    queue.append(ref)

        # Check if this var is an @app.function
        if var in function_names:
            required_functions.add(var)

    # Also check each required cell's code for function calls
    for idx in list(required_indices):
        cell = parsed.cells[idx]
        for func_name in function_names:
            if func_name in cell.code:
                required_functions.add(func_name)

    return sorted(required_indices), required_functions


def inject_snapshot(
    cell_code: str, target_var: str, target_line: int, cell_start_line: int
) -> str:
    """
    Inject a snapshot variable to capture intermediate state.

    If target_line points to a specific line within the cell, we insert
    a snapshot assignment after that line to capture the variable's state.

    Args:
        cell_code: The full cell code
        target_var: The variable to snapshot
        target_line: The line number to snapshot after (1-indexed, file-relative)
        cell_start_line: The line number where this cell starts in the file

    Returns:
        Modified cell code with snapshot injection
    """
    lines = cell_code.splitlines(keepends=True)
    # Convert file-relative line to cell-relative (0-indexed)
    relative_line = target_line - cell_start_line

    if relative_line < 0 or relative_line >= len(lines):
        # Line not in this cell, return unchanged
        return cell_code

    # Detect if target line is part of a method chain
    # Look for pattern like df = ( ... .pipe(x) ... )
    target_content = lines[relative_line] if relative_line < len(lines) else ""

    # Check if this is a .pipe() call or similar method chain
    if ".pipe(" in target_content or re.search(r"\.\w+\(", target_content):
        # Try to break the method chain
        return _break_method_chain(lines, relative_line, target_var)

    # Simple case: insert snapshot after target line
    # Determine indentation from the target line
    indent_match = re.match(r"^(\s*)", lines[relative_line])
    indent = indent_match.group(1) if indent_match else "    "

    snapshot_line = f"{indent}_viz_snapshot_{target_var} = {target_var}.copy() if hasattr({target_var}, 'copy') else {target_var}\n"

    # Insert after the target line
    insert_pos = relative_line + 1
    lines.insert(insert_pos, snapshot_line)

    return "".join(lines)


def _break_method_chain(
    lines: list[str], target_line_idx: int, target_var: str
) -> str:
    """
    Break a method chain at the target line and inject a snapshot.

    For a chain like:
        df = (
            df_.copy()
            .pipe(add_channel)
            .pipe(add_channel_type)  <- target
            .pipe(select_columns)
        )

    Produces:
        df = df_.copy()
        df = df.pipe(add_channel)
        df = df.pipe(add_channel_type)
        _viz_snapshot_df = df.copy()
        df = df.pipe(select_columns)
    """
    # This is a complex transformation - for now, just insert a comment
    # indicating the snapshot point. A full implementation would need to
    # parse the AST more carefully.

    # Find the assignment line (df = ...)
    chain_start = None
    for i in range(target_line_idx, -1, -1):
        if "=" in lines[i] and "==" not in lines[i]:
            chain_start = i
            break

    if chain_start is None:
        return "".join(lines)

    # For now, add a snapshot after the full chain completes with a note
    # A more sophisticated version could actually break the chain
    indent_match = re.match(r"^(\s*)", lines[target_line_idx])
    indent = indent_match.group(1) if indent_match else "    "

    # Find the end of the method chain (closing paren and return)
    chain_end = target_line_idx
    paren_depth = 0
    for i in range(chain_start, len(lines)):
        paren_depth += lines[i].count("(") - lines[i].count(")")
        if paren_depth <= 0 and (lines[i].strip().endswith(")") or "return" in lines[i]):
            chain_end = i
            break

    # Insert snapshot right before return statement if present
    for i in range(chain_end, len(lines)):
        if "return" in lines[i]:
            snapshot_line = f"{indent}_viz_snapshot_{target_var} = {target_var}.copy() if hasattr({target_var}, 'copy') else {target_var}\n"
            lines.insert(i, snapshot_line)
            break

    return "".join(lines)


def assemble_pruned_notebook(
    parsed: ParsedNotebook,
    required_indices: list[int],
    required_functions: set[str],
    plot_code: str,
    target_var: str | None = None,
    target_line: int | None = None,
) -> str:
    """
    Assemble a pruned notebook with only required cells + plot code.

    Args:
        parsed: The parsed notebook structure
        required_indices: Indices of cells to include
        required_functions: Names of @app.functions to include
        plot_code: The plotting code to inject as a new cell
        target_var: If set, the variable to potentially snapshot
        target_line: If set with target_var, inject snapshot at this line

    Returns:
        Complete Python script ready to execute
    """
    parts = []

    # 1. Preamble
    parts.append(parsed.preamble)

    # 2. Setup block
    if parsed.setup_code:
        parts.append("\nwith app.setup:\n")
        # Indent the setup code properly
        setup_lines = parsed.setup_code.splitlines(keepends=True)
        for line in setup_lines:
            if line.strip():  # Non-empty line
                # Check if already indented
                if not line.startswith("    "):
                    parts.append("    " + line)
                else:
                    parts.append(line)
            else:
                parts.append(line)
        parts.append("\n")

    # 3. Classes (all classes are included as they might be needed)
    for cls in parsed.classes:
        parts.append("\n" + cls.code + "\n")

    # 4. Required @app.functions
    for func in parsed.functions:
        if func.name in required_functions:
            parts.append("\n" + func.code + "\n")

    # 5. Required cells
    for idx in required_indices:
        cell = parsed.cells[idx]
        cell_code = cell.code

        # Inject snapshot if needed
        if target_var and target_line and target_var in cell.defs:
            if cell.start_line <= target_line <= cell.end_line:
                cell_code = inject_snapshot(
                    cell_code, target_var, target_line, cell.start_line
                )

        parts.append("\n" + cell_code + "\n")

    # 6. Plotting cell
    # Wrap plot_code in an @app.cell
    # Determine what variables the plot code needs - use target_var
    if target_var and target_line:
        refs = f"_viz_snapshot_{target_var}"
    elif target_var:
        refs = target_var
    else:
        refs = "_"

    plot_cell = f'''
@app.cell
def _({refs}):
    # Viz skill injected plotting code
{_indent_code(plot_code, "    ")}
    return
'''
    parts.append(plot_cell)

    # 7. Main block
    if parsed.main_block:
        parts.append("\n" + parsed.main_block)
    else:
        parts.append('\nif __name__ == "__main__":\n    app.run()\n')

    return "".join(parts)


def _indent_code(code: str, indent: str) -> str:
    """Add indentation to each line of code."""
    lines = code.splitlines(keepends=True)
    indented = []
    for line in lines:
        if line.strip():
            indented.append(indent + line)
        else:
            indented.append(line)
    return "".join(indented)


def get_python_command(cwd: Path) -> list[str]:
    """
    Determine Python command based on environment.

    1. If VIZ_PYTHON_CMD env var is set, use that
    2. If cwd has a uv project (pyproject.toml or uv.lock), use 'uv run python'
    3. Otherwise use sys.executable (the Python running viz_runner.py)
    """
    # Check env var first
    env_cmd = os.environ.get("VIZ_PYTHON_CMD")
    if env_cmd:
        return shlex.split(env_cmd)

    # Check for uv project markers
    uv_markers = [cwd / "pyproject.toml", cwd / "uv.lock"]
    if any(marker.exists() for marker in uv_markers):
        return ["uv", "run", "python"]

    return [sys.executable]


def run_marimo_notebook(
    notebook_path: Path,
    target_vars: list[str],
    plot_code: str,
    viz_id: str,
    description: str | None = None,
    target_line: int | None = None,
) -> tuple[bool, str, Path | None]:
    """
    Execute a marimo notebook with pruned cells and injected plot code.

    Args:
        notebook_path: Path to the original marimo notebook
        target_vars: Variables to extract from the notebook
        plot_code: Plotting code to inject
        viz_id: ID for the visualization
        description: Optional description
        target_line: Optional line number for intermediate snapshot

    Returns:
        (success, message, png_path)
    """
    ensure_viz_dir()

    try:
        # Parse the notebook
        parsed = parse_marimo_notebook(notebook_path)

        # Get required cells
        required_indices, required_functions = get_required_cells(parsed, target_vars)

        if not required_indices:
            return False, f"Could not find cells defining: {target_vars}", None

        # Assemble pruned notebook
        target_var = target_vars[0] if target_vars else None
        pruned_code = assemble_pruned_notebook(
            parsed,
            required_indices,
            required_functions,
            plot_code,
            target_var=target_var,
            target_line=target_line,
        )

        # Write to temp location
        script_path = VIZ_DIR / f"{viz_id}.py"
        png_path = VIZ_DIR / f"{viz_id}.png"

        # Inject savefig into the plot code
        pruned_code = inject_savefig(pruned_code, str(png_path))

        script_path.write_text(pruned_code)

        # Execute with cwd set to original notebook's directory
        cwd = notebook_path.parent
        python_cmd = get_python_command(cwd)

        process = subprocess.Popen(
            [*python_cmd, str(script_path)],
            cwd=cwd,  # Critical: run from notebook's directory
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        # Poll for PNG
        max_wait = 30.0  # Longer timeout for notebooks with DB queries
        poll_interval = 0.2
        waited = 0.0

        while waited < max_wait:
            if png_path.exists():
                # Write metadata
                json_path = VIZ_DIR / f"{viz_id}.json"
                metadata = {
                    "id": viz_id,
                    "desc": description,
                    "png": str(png_path),
                    "script": str(script_path),
                    "source_notebook": str(notebook_path),
                    "target_vars": target_vars,
                    "created": datetime.now().isoformat(timespec="seconds"),
                    "pid": process.pid,
                }
                json_path.write_text(json.dumps(metadata, indent=2))
                return True, "Plot generated successfully", png_path

            time.sleep(poll_interval)
            waited += poll_interval

            # Check if process failed
            if process.poll() is not None:
                stderr = process.stderr.read().decode() if process.stderr else ""
                module_error = format_module_error(stderr, python_cmd)
                if module_error:
                    return False, module_error, None
                return False, f"Script failed: {stderr}", None

        return False, "Timeout waiting for plot (script may still be running)", None

    except Exception as e:
        return False, f"Error: {e}", None


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


def format_module_error(stderr: str, python_cmd: list[str]) -> str | None:
    """
    Detect ModuleNotFoundError and return a clear, actionable error message.
    Returns None if not a module error.
    """
    match = re.search(r"ModuleNotFoundError: No module named ['\"]?([^'\"]+)['\"]?", stderr)
    if match:
        module = match.group(1)
        cmd_str = " ".join(python_cmd)
        return f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  MISSING MODULE: {module:<59} ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  The viz skill's Python environment is missing required packages.            ║
║                                                                              ║
║  To fix this, either:                                                        ║
║                                                                              ║
║  1. Restart Claude Code with the correct Python environment activated:       ║
║     $ source /path/to/your/venv/bin/activate && claude                       ║
║                                                                              ║
║  2. Or configure viz_runner.py to use a different Python command:            ║
║     Set VIZ_PYTHON_CMD environment variable, e.g.:                           ║
║     $ export VIZ_PYTHON_CMD="uv run python"                                  ║
║                                                                              ║
║  Python command: {cmd_str:<57} ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
    return None


def get_python_cmd() -> list[str]:
    """Get the Python command to use for running scripts."""
    cmd = os.environ.get("VIZ_PYTHON_CMD")
    if cmd:
        return shlex.split(cmd)
    return [sys.executable]


def run_script_background(script_path: Path, png_path: Path) -> tuple[bool, int, str]:
    """
    Execute the script in background and wait for PNG to be created.
    Returns (success, pid, message).

    The script runs as a detached process so plt.show() doesn't block.
    Since savefig() is injected BEFORE plt.show(), the PNG gets created
    immediately while the interactive window stays open.
    """
    try:
        python_cmd = get_python_cmd()

        # Start script as detached background process
        # Use caller's cwd (not VIZ_DIR) so uv can find pyproject.toml
        process = subprocess.Popen(
            [*python_cmd, str(script_path)],
            start_new_session=True,  # Detach from terminal
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
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
                # Check for module errors and provide helpful message
                module_error = format_module_error(stderr, python_cmd)
                if module_error:
                    return False, 0, module_error
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

    # Marimo notebook support
    parser.add_argument("--marimo", action="store_true", help="Enable marimo notebook mode")
    parser.add_argument("--notebook", dest="notebook_path", help="Path to marimo notebook (.nb.py)")
    parser.add_argument("--target-var", dest="target_var", help="Variable to extract from notebook")
    parser.add_argument("--target-line", dest="target_line", type=int, help="Line number for intermediate state capture")

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

    # Handle marimo notebook mode
    if args.marimo:
        if not args.notebook_path:
            print("error: --marimo requires --notebook path", file=sys.stderr)
            sys.exit(1)
        if not args.target_var:
            print("error: --marimo requires --target-var", file=sys.stderr)
            sys.exit(1)

        notebook_path = Path(args.notebook_path)
        if not notebook_path.exists():
            print(f"error: Notebook not found: {notebook_path}", file=sys.stderr)
            sys.exit(1)

        # Read plot code from stdin
        if sys.stdin.isatty():
            print("error: Pipe plot code to stdin for marimo mode", file=sys.stderr)
            sys.exit(1)
        plot_code = sys.stdin.read()

        if not plot_code.strip():
            print("error: Empty plot code provided", file=sys.stderr)
            sys.exit(1)

        # Get unique ID
        final_id = get_unique_id(args.suggested_id)

        # Run the marimo notebook
        success, message, png_path = run_marimo_notebook(
            notebook_path=notebook_path,
            target_vars=[args.target_var],
            plot_code=plot_code,
            viz_id=final_id,
            description=args.description,
            target_line=args.target_line,
        )

        # Print human-readable output
        print(f"Plot: {final_id}")
        if args.description:
            print(f'  "{args.description}"')
        if png_path:
            print(f"  png: {png_path}")
        print(f"  source: {notebook_path}")

        if not success:
            print(f"  error: {message}")

        sys.exit(0 if success else 1)

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
