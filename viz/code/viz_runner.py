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
from typing import Protocol

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


@dataclass
class VizMetadata:
    """Metadata for a visualization artifact."""

    viz_id: str
    description: str | None
    png_path: Path
    script_path: Path
    pid: int
    source_notebook: Path | None = None
    target_vars: list[str] | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = {
            "id": self.viz_id,
            "desc": self.description,
            "png": str(self.png_path),
            "script": str(self.script_path),
            "created": datetime.now().isoformat(timespec="seconds"),
            "pid": self.pid,
        }
        if self.source_notebook:
            data["source_notebook"] = str(self.source_notebook)
        if self.target_vars:
            data["target_vars"] = self.target_vars
        return data

    def write(self, viz_dir: Path = VIZ_DIR) -> Path:
        """Write metadata to JSON file."""
        json_path = viz_dir / f"{self.viz_id}.json"
        json_path.write_text(json.dumps(self.to_dict(), indent=2))
        return json_path


@dataclass
class PreparedNotebook:
    """Result of parsing and preparing a marimo notebook for execution."""

    parsed: ParsedNotebook
    required_indices: list[int]
    required_functions: set[str]
    target_var: str | None
    cwd: Path


# ============================================================================
# Source Handler Architecture
# ============================================================================


class SourceHandler(Protocol):
    """Interface for handlers that know how to build scripts from different source types."""

    def build_script(
        self,
        action_code: str,
        source_path: Path | None = None,
        target_var: str | None = None,
        **kwargs,
    ) -> tuple[str, Path | None]:
        """
        Build an executable Python script that prepares data and runs action_code.

        The action_code could be plotting code, show/inspection code, or any other
        code that operates on the target variable.

        Args:
            action_code: Code to execute (plotting, showing, etc.)
            source_path: Optional path to source file (notebook, SQL file, etc.)
            target_var: Optional variable name to extract from source
            **kwargs: Handler-specific options

        Returns:
            (script_content, working_directory)
            - script_content: Complete Python script ready to execute
            - working_directory: Directory to run script from (or None for cwd)
        """
        ...

    def validate_args(self, args: argparse.Namespace) -> tuple[bool, str]:
        """
        Validate that required arguments are present.

        Returns:
            (valid, error_message)
        """
        ...


class DefaultHandler:
    """Default handler - action_code is the complete script."""

    def build_script(
        self,
        action_code: str,
        source_path: Path | None = None,
        target_var: str | None = None,
        **kwargs,
    ) -> tuple[str, Path | None]:
        """For default handler, action_code IS the complete script."""
        return action_code, None

    def validate_args(self, args: argparse.Namespace) -> tuple[bool, str]:
        """Default handler has no special requirements."""
        return True, ""


class MarimoHandler:
    """Handler for marimo notebooks - parses and assembles pruned scripts."""

    def build_script(
        self,
        action_code: str,
        source_path: Path | None = None,
        target_var: str | None = None,
        target_line: int | None = None,
        **kwargs,
    ) -> tuple[str, Path | None]:
        """
        Build a script by parsing marimo notebook and resolving dependencies.

        Args:
            action_code: Code to execute (plotting, showing, etc.)
            source_path: Path to the marimo notebook
            target_var: Variable to extract from the notebook
            target_line: Optional line number for intermediate state capture

        Returns:
            (script_content, working_directory)

        Raises:
            ValueError: If notebook parsing fails or target variable not found
        """
        if source_path is None:
            raise ValueError("MarimoHandler requires source_path (notebook path)")
        if target_var is None:
            raise ValueError("MarimoHandler requires target_var")

        prep = prepare_notebook(source_path, [target_var])
        if isinstance(prep, tuple):
            raise ValueError(prep[1])

        script = assemble_pruned_notebook(
            prep.parsed,
            prep.required_indices,
            prep.required_functions,
            action_code,
            target_var=prep.target_var,
            target_line=target_line,
        )
        return script, prep.cwd

    def validate_args(self, args: argparse.Namespace) -> tuple[bool, str]:
        """Validate marimo-specific arguments."""
        if not getattr(args, "notebook_path", None):
            return False, "--marimo requires --notebook path"
        if not getattr(args, "target_var", None):
            return False, "--marimo requires --target-var"
        if not Path(args.notebook_path).exists():
            return False, f"Notebook not found: {args.notebook_path}"
        return True, ""


# Handler registry
HANDLERS: dict[str, type[SourceHandler]] = {
    "default": DefaultHandler,
    "marimo": MarimoHandler,
}


def get_handler(args: argparse.Namespace) -> SourceHandler:
    """Select handler based on CLI args."""
    if getattr(args, "marimo", False):
        return MarimoHandler()
    # Future: elif args.sql: return SQLHandler()
    return DefaultHandler()


def run_plot(
    handler: SourceHandler,
    plot_code: str,
    viz_id: str,
    description: str | None = None,
    source_path: Path | None = None,
    target_var: str | None = None,
    **handler_kwargs,
) -> tuple[bool, str, Path | None]:
    """
    Core plotting function - uses handler to build script, then executes.

    Args:
        handler: The SourceHandler to use for building the script
        plot_code: The plotting code (or complete script for DefaultHandler)
        viz_id: ID for the visualization
        description: Optional description
        source_path: Optional source file (for MarimoHandler, etc.)
        target_var: Optional target variable (for MarimoHandler, etc.)
        **handler_kwargs: Additional handler-specific options

    Returns:
        (success, message, png_path)
    """
    ensure_viz_dir()

    # Build the script using the handler
    try:
        script_content, cwd = handler.build_script(
            plot_code,
            source_path=source_path,
            target_var=target_var,
            **handler_kwargs,
        )
    except ValueError as e:
        return False, str(e), None

    # Determine paths
    script_path = VIZ_DIR / f"{viz_id}.py"
    png_path = VIZ_DIR / f"{viz_id}.png"

    # Inject savefig
    script_content = inject_savefig(script_content, str(png_path))
    script_path.write_text(script_content)

    # Execute
    python_cmd = get_python_command(cwd)

    process = subprocess.Popen(
        [*python_cmd, str(script_path)],
        cwd=cwd,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    # Poll for PNG (longer timeout for notebooks with DB queries)
    max_wait = 30.0 if source_path else 3.0
    result = poll_for_file(
        process, png_path, python_cmd, max_wait=max_wait, poll_interval=0.2
    )

    if result.success:
        VizMetadata(
            viz_id=viz_id,
            description=description,
            png_path=png_path,
            script_path=script_path,
            pid=result.process.pid,
            source_notebook=source_path if isinstance(handler, MarimoHandler) else None,
            target_vars=[target_var] if target_var else None,
        ).write()
        return True, "Plot generated successfully", png_path

    return False, result.message, None


def generate_show_code(target_var: str, num_rows: int = 5) -> str:
    """
    Generate code to display dataframe info to stdout.

    Args:
        target_var: Name of the variable to inspect
        num_rows: Number of rows to display

    Returns:
        Python code string that prints dataframe info
    """
    return f'''
_var = {target_var}
print(f"Shape: {{_var.shape}}")
print(f"Columns: {{list(_var.columns)}}")
print(f"\\nDtypes:")
print(_var.dtypes.to_string())
print(f"\\nFirst {num_rows} rows:")
if hasattr(_var, 'to_string'):
    print(_var.head({num_rows}).to_string())
else:
    print(_var.head({num_rows}))
'''


def run_show(
    handler: SourceHandler,
    target_var: str,
    source_path: Path | None = None,
    num_rows: int = 5,
    **handler_kwargs,
) -> tuple[bool, str]:
    """
    Execute a script to show/inspect data and capture output.

    Unlike run_plot() which backgrounds and polls for a PNG, this runs
    synchronously and captures stdout.

    Args:
        handler: The SourceHandler to use for building the script
        target_var: Variable to inspect
        source_path: Optional source file (for MarimoHandler, etc.)
        num_rows: Number of rows to display
        **handler_kwargs: Additional handler-specific options

    Returns:
        (success, output_or_error)
    """
    ensure_viz_dir()

    # Generate the show code
    show_code = generate_show_code(target_var, num_rows)

    # Build the script using the handler
    try:
        script_content, cwd = handler.build_script(
            show_code,
            source_path=source_path,
            target_var=target_var,
            **handler_kwargs,
        )
    except ValueError as e:
        return False, str(e)

    # Write to temp location
    script_path = VIZ_DIR / "_show_temp.py"
    script_path.write_text(script_content)

    try:
        # Execute synchronously and capture output
        python_cmd = get_python_command(cwd)

        result = subprocess.run(
            [*python_cmd, str(script_path)],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Clean up temp file
        script_path.unlink(missing_ok=True)

        if result.returncode != 0:
            # Check for module errors
            module_error = format_module_error(result.stderr, python_cmd)
            if module_error:
                return False, module_error
            return False, f"Script failed:\n{result.stderr}"

        return True, result.stdout

    except subprocess.TimeoutExpired:
        script_path.unlink(missing_ok=True)
        return False, "Timeout executing script"
    except Exception as e:
        script_path.unlink(missing_ok=True)
        return False, f"Error: {e}"


def prepare_notebook(
    notebook_path: Path,
    target_vars: list[str],
) -> PreparedNotebook | tuple[bool, str]:
    """
    Parse notebook and resolve dependencies.

    Returns PreparedNotebook on success, or (False, error_message) on failure.
    """
    parsed = parse_marimo_notebook(notebook_path)
    required_indices, required_functions = get_required_cells(parsed, target_vars)

    if not required_indices:
        return (False, f"Could not find cells defining: {target_vars}")

    return PreparedNotebook(
        parsed=parsed,
        required_indices=required_indices,
        required_functions=required_functions,
        target_var=target_vars[0] if target_vars else None,
        cwd=notebook_path.parent,
    )


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


def _extract_node_source(
    node: ast.FunctionDef | ast.ClassDef, source_lines: list[str]
) -> tuple[str, int, int]:
    """
    Extract source code for an AST node, accounting for decorators.

    Returns: (code, start_line, end_line)
    """
    start_line = node.lineno
    if hasattr(node, "decorator_list"):
        for decorator in node.decorator_list:
            start_line = min(start_line, decorator.lineno)
    end_line = node.end_lineno or node.lineno
    code = "".join(source_lines[start_line - 1 : end_line])
    return code, start_line, end_line


def _parse_cell(node: ast.FunctionDef, source_lines: list[str]) -> MarimoCell:
    """Parse an @app.cell decorated function into a MarimoCell."""
    # Get refs from function parameters
    refs = [arg.arg for arg in node.args.args if arg.arg != "_"]

    # Get defs from return statement
    defs = []
    for stmt in ast.walk(node):
        if isinstance(stmt, ast.Return) and stmt.value:
            if isinstance(stmt.value, ast.Tuple):
                for elt in stmt.value.elts:
                    if isinstance(elt, ast.Name):
                        defs.append(elt.id)

    code, start_line, end_line = _extract_node_source(node, source_lines)

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
    code, start_line, end_line = _extract_node_source(node, source_lines)
    return MarimoFunction(
        name=node.name, code=code, start_line=start_line, end_line=end_line
    )


def _parse_class(node: ast.ClassDef, source_lines: list[str]) -> MarimoClass:
    """Parse a class definition."""
    code, start_line, end_line = _extract_node_source(node, source_lines)
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


# ============================================================================
# Import Deduplication (prevents multiple-definitions errors)
# ============================================================================


def extract_setup_imports(setup_code: str) -> dict[str, str]:
    """
    Extract import statements from the setup block.

    Returns a dict mapping imported names to their import statements.
    E.g., {"np": "import numpy as np", "pd": "import pandas as pd"}
    """
    import textwrap

    imports = {}

    # Dedent the code first to handle indented setup blocks
    dedented = textwrap.dedent(setup_code)

    try:
        tree = ast.parse(dedented)
    except SyntaxError:
        # Fall back to regex if AST parsing fails
        return _extract_imports_regex(setup_code)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name
                imports[name] = f"import {alias.name}" + (f" as {alias.asname}" if alias.asname else "")

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                name = alias.asname or alias.name
                imports[name] = f"from {module} import {alias.name}" + (f" as {alias.asname}" if alias.asname else "")

    return imports


def _extract_imports_regex(code: str) -> dict[str, str]:
    """Fallback regex-based import extraction."""
    imports = {}

    # Match: import X as Y, import X
    import_pattern = re.compile(r'^import\s+(\w+)(?:\s+as\s+(\w+))?', re.MULTILINE)
    for match in import_pattern.finditer(code):
        module = match.group(1)
        alias = match.group(2) or module
        imports[alias] = match.group(0)

    # Match: from X import Y as Z, from X import Y
    from_pattern = re.compile(r'^from\s+[\w.]+\s+import\s+(\w+)(?:\s+as\s+(\w+))?', re.MULTILINE)
    for match in from_pattern.finditer(code):
        name = match.group(1)
        alias = match.group(2) or name
        imports[alias] = match.group(0)

    return imports


def strip_imports_from_action_code(action_code: str, setup_imports: dict[str, str]) -> str:
    """
    Remove import statements from action code that are already in setup block.

    This prevents marimo's multiple-definitions error when injecting plotting
    code that imports modules already imported in app.setup.

    Args:
        action_code: The plotting/action code to inject
        setup_imports: Dict of {name: import_statement} from setup block

    Returns:
        Action code with duplicate imports removed
    """
    lines = action_code.splitlines(keepends=True)
    result_lines = []

    for line in lines:
        stripped = line.strip()

        # Check if this is an import line
        if stripped.startswith('import ') or stripped.startswith('from '):
            imported_names = _extract_imported_names_from_line(stripped)

            # Check if ALL names in this import are already in setup
            all_in_setup = all(name in setup_imports for name in imported_names)

            if all_in_setup and imported_names:
                # Skip this import line - it's already in setup
                continue

        result_lines.append(line)

    return ''.join(result_lines)


def _extract_imported_names_from_line(import_line: str) -> list[str]:
    """
    Extract the names that would be bound by an import statement.

    Examples:
        'import numpy as np' -> ['np']
        'import numpy' -> ['numpy']
        'from os import path' -> ['path']
        'from typing import List, Dict' -> ['List', 'Dict']
    """
    import_line = import_line.strip()

    # Handle: import X as Y
    match = re.match(r'^import\s+(\w+)(?:\s+as\s+(\w+))?$', import_line)
    if match:
        return [match.group(2) or match.group(1)]

    # Handle: from X import Y, Z, ...
    match = re.match(r'^from\s+[\w.]+\s+import\s+(.+)$', import_line)
    if match:
        names = []
        for part in match.group(1).split(','):
            part = part.strip()
            alias_match = re.match(r'(\w+)(?:\s+as\s+(\w+))?', part)
            if alias_match:
                names.append(alias_match.group(2) or alias_match.group(1))
        return names

    return []


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

    # Strip duplicate imports from plot_code to prevent multiple-definitions errors
    # This is done BEFORE injection to avoid marimo check failures
    if parsed.setup_code:
        setup_imports = extract_setup_imports(parsed.setup_code)
        plot_code = strip_imports_from_action_code(plot_code, setup_imports)

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


def validate_python_env(python_cmd: list[str], required_module: str = "matplotlib") -> bool:
    """
    Test if a Python environment can import a required module.

    Returns True if import succeeds, False otherwise.
    """
    try:
        result = subprocess.run(
            [*python_cmd, "-c", f"import {required_module}"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def get_python_command(cwd: Path | None = None) -> list[str]:
    """
    Determine Python command with fallback chain and import validation.

    Priority:
    1. VIZ_PYTHON_CMD env var (explicit override, no validation)
    2. Project environment (cwd with uv markers) - validated
    3. System Python on PATH - validated
    4. Viz skill's own environment - guaranteed fallback
    """
    # Explicit override - trust the user
    env_cmd = os.environ.get("VIZ_PYTHON_CMD")
    if env_cmd:
        return shlex.split(env_cmd)

    # Try project's environment first
    if cwd is not None:
        uv_markers = [cwd / "pyproject.toml", cwd / "uv.lock"]
        if any(marker.exists() for marker in uv_markers):
            project_cmd = ["uv", "run", "--directory", str(cwd), "python"]
            if validate_python_env(project_cmd):
                return project_cmd

    # Try system Python on PATH
    system_cmd = ["python"]
    if validate_python_env(system_cmd):
        return system_cmd

    # Fall back to viz skill's own environment (guaranteed deps)
    viz_skill_dir = Path(__file__).parent
    return ["uv", "run", "--directory", str(viz_skill_dir), "python"]


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
        # Prepare the notebook
        prep = prepare_notebook(notebook_path, target_vars)
        if isinstance(prep, tuple):
            return prep[0], prep[1], None

        # Assemble pruned notebook
        pruned_code = assemble_pruned_notebook(
            prep.parsed,
            prep.required_indices,
            prep.required_functions,
            plot_code,
            target_var=prep.target_var,
            target_line=target_line,
        )

        # Write to temp location
        script_path = VIZ_DIR / f"{viz_id}.py"
        png_path = VIZ_DIR / f"{viz_id}.png"

        # Inject savefig into the plot code
        pruned_code = inject_savefig(pruned_code, str(png_path))

        script_path.write_text(pruned_code)

        # Execute with cwd set to original notebook's directory
        python_cmd = get_python_command(prep.cwd)

        process = subprocess.Popen(
            [*python_cmd, str(script_path)],
            cwd=prep.cwd,  # Critical: run from notebook's directory
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        # Poll for PNG (longer timeout for notebooks with DB queries)
        result = poll_for_file(
            process, png_path, python_cmd,
            max_wait=30.0, poll_interval=0.2
        )

        if result.success:
            VizMetadata(
                viz_id=viz_id,
                description=description,
                png_path=png_path,
                script_path=script_path,
                pid=result.process.pid,
                source_notebook=notebook_path,
                target_vars=target_vars,
            ).write()
            return True, "Plot generated successfully", png_path

        return False, result.message, None

    except Exception as e:
        return False, f"Error: {e}", None


def run_marimo_show(
    notebook_path: Path,
    target_vars: list[str],
    num_rows: int = 5,
) -> tuple[bool, str]:
    """
    Execute a marimo notebook and print dataframe info to console.

    Args:
        notebook_path: Path to the original marimo notebook
        target_vars: Variables to extract from the notebook
        num_rows: Number of rows to display (default: 5)

    Returns:
        (success, output_or_error)
    """
    try:
        # Prepare the notebook
        prep = prepare_notebook(notebook_path, target_vars)
        if isinstance(prep, tuple):
            return prep

        # Generate show code instead of plot code
        # Don't import pandas - it's typically already in the setup block
        show_code = f'''
_var = {prep.target_var}
print(f"Shape: {{_var.shape}}")
print(f"Columns: {{list(_var.columns)}}")
print(f"\\nDtypes:")
print(_var.dtypes.to_string())
print(f"\\nFirst {num_rows} rows:")
if hasattr(_var, 'to_string'):
    print(_var.head({num_rows}).to_string())
else:
    print(_var.head({num_rows}))
'''

        # Assemble pruned notebook with show code
        pruned_code = assemble_pruned_notebook(
            prep.parsed,
            prep.required_indices,
            prep.required_functions,
            show_code,
            target_var=prep.target_var,
            target_line=None,
        )

        # Write to temp location
        script_path = VIZ_DIR / f"_show_temp.py"
        ensure_viz_dir()
        script_path.write_text(pruned_code)

        # Execute with cwd set to original notebook's directory
        python_cmd = get_python_command(prep.cwd)

        result = subprocess.run(
            [*python_cmd, str(script_path)],
            cwd=prep.cwd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Clean up temp file
        script_path.unlink(missing_ok=True)

        if result.returncode != 0:
            # Check for module errors
            module_error = format_module_error(result.stderr, python_cmd)
            if module_error:
                return False, module_error
            return False, f"Script failed:\n{result.stderr}"

        return True, result.stdout

    except subprocess.TimeoutExpired:
        return False, "Timeout executing notebook"
    except Exception as e:
        return False, f"Error: {e}"


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


@dataclass
class PollResult:
    """Result from polling a subprocess for file creation."""

    success: bool
    message: str
    process: subprocess.Popen


def poll_for_file(
    process: subprocess.Popen,
    target_file: Path,
    python_cmd: list[str],
    max_wait: float = 3.0,
    poll_interval: float = 0.1,
) -> PollResult:
    """
    Poll a subprocess, waiting for a target file to be created.

    Returns early if:
    - Target file appears (success)
    - Process exits with error (failure)
    - Timeout reached (failure, but process may still be running)
    """
    waited = 0.0
    while waited < max_wait:
        if target_file.exists():
            return PollResult(success=True, message="File created", process=process)

        time.sleep(poll_interval)
        waited += poll_interval

        if process.poll() is not None:
            stderr = process.stderr.read().decode() if process.stderr else ""
            module_error = format_module_error(stderr, python_cmd)
            error_msg = module_error or f"Script failed: {stderr}"
            return PollResult(success=False, message=error_msg, process=process)

    return PollResult(
        success=False,
        message="Timeout waiting for file (process may still be running)",
        process=process,
    )


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


def run_script_background(script_path: Path, png_path: Path) -> tuple[bool, int, str]:
    """
    Execute the script in background and wait for PNG to be created.
    Returns (success, pid, message).

    The script runs as a detached process so plt.show() doesn't block.
    Since savefig() is injected BEFORE plt.show(), the PNG gets created
    immediately while the interactive window stays open.
    """
    try:
        python_cmd = get_python_command()

        # Start script as detached background process
        # Use caller's cwd (not VIZ_DIR) so uv can find pyproject.toml
        process = subprocess.Popen(
            [*python_cmd, str(script_path)],
            start_new_session=True,  # Detach from terminal
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        # Poll for PNG (savefig happens before plt.show)
        result = poll_for_file(process, png_path, python_cmd)

        if result.success:
            return True, result.process.pid, "Plot window opened"

        # On failure, return 0 for pid if process failed, otherwise actual pid
        pid = 0 if result.process.poll() is not None else result.process.pid
        return False, pid, result.message

    except Exception as e:
        return False, 0, f"Error: {e}"


def handle_clean() -> int:
    """Handle --clean command. Returns exit code."""
    ensure_viz_dir()
    count = 0
    for f in VIZ_DIR.iterdir():
        if f.is_file():
            f.unlink()
            count += 1
    print(f"Cleaned {count} files from {VIZ_DIR}")
    return 0


def handle_list() -> int:
    """Handle --list command. Returns exit code."""
    ensure_viz_dir()
    json_files = sorted(VIZ_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not json_files:
        print("No visualizations found")
        return 0

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
    return 0


def handle_marimo_show(args: argparse.Namespace) -> int:
    """Handle --marimo --show command. Returns exit code."""
    notebook_path = Path(args.notebook_path)

    handler = MarimoHandler()
    success, output = run_show(
        handler=handler,
        target_var=args.target_var,
        source_path=notebook_path,
        num_rows=args.rows,
    )

    if success:
        print(output)
    else:
        print(f"error: {output}", file=sys.stderr)

    return 0 if success else 1


def handle_marimo_plot(args: argparse.Namespace, plot_code: str) -> int:
    """Handle --marimo plot command. Returns exit code."""
    notebook_path = Path(args.notebook_path)
    final_id = get_unique_id(args.suggested_id)

    handler = MarimoHandler()
    success, message, png_path = run_plot(
        handler=handler,
        plot_code=plot_code,
        viz_id=final_id,
        description=args.description,
        source_path=notebook_path,
        target_var=args.target_var,
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

    return 0 if success else 1


def handle_standalone_script(args: argparse.Namespace, script_content: str) -> int:
    """Handle standalone script execution. Returns exit code."""
    final_id = get_unique_id(args.suggested_id)
    png_path = VIZ_DIR / f"{final_id}.png"

    handler = DefaultHandler()
    success, message, png_path_result = run_plot(
        handler=handler,
        plot_code=script_content,
        viz_id=final_id,
        description=args.description,
    )

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

    return 0 if success else 1


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
    parser.add_argument("--show", action="store_true", help="Show mode: print dataframe info to console instead of plotting")
    parser.add_argument("--rows", dest="rows", type=int, default=5, help="Number of rows to display in show mode (default: 5)")

    args = parser.parse_args()

    # Handle clean action
    if args.clean:
        sys.exit(handle_clean())

    # Handle list action
    if args.list:
        sys.exit(handle_list())

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

        # Handle --show mode (print dataframe to console)
        if args.show:
            sys.exit(handle_marimo_show(args))

        # Read plot code from stdin
        if sys.stdin.isatty():
            print("error: Pipe plot code to stdin for marimo mode", file=sys.stderr)
            sys.exit(1)
        plot_code = sys.stdin.read()

        if not plot_code.strip():
            print("error: Empty plot code provided", file=sys.stderr)
            sys.exit(1)

        sys.exit(handle_marimo_plot(args, plot_code))

    # Handle standalone script mode
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

    sys.exit(handle_standalone_script(args, script_content))


if __name__ == "__main__":
    main()
