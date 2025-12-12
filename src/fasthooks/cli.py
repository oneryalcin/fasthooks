"""CLI for fasthooks - Delightful Claude Code hooks."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer
from rich import print

app = typer.Typer(
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
)

HOOKS_TEMPLATE = '''\
# /// script
# dependencies = ["fasthooks"]
# ///
"""Claude Code hooks."""
from fasthooks import HookApp, allow, deny

app = HookApp()


@app.pre_tool("Bash")
def check_bash(event):
    """Block dangerous bash commands."""
    if "rm -rf" in event.command:
        return deny("Dangerous command blocked")
    return allow()


@app.on_stop()
def on_stop(event):
    """Handle stop events."""
    return allow()


if __name__ == "__main__":
    app.run()
'''

PYPROJECT_TEMPLATE = '''\
[project]
name = "{name}"
version = "0.1.0"
description = "Claude Code hooks"
requires-python = ">=3.11"
dependencies = [
    "fasthooks",
]

[project.optional-dependencies]
dev = [
    "pytest",
]
'''

SETTINGS_TEMPLATE = '''\
{{
  "hooks": {{
    "PreToolUse": [
      {{
        "matcher": "*",
        "hooks": [
          {{
            "type": "command",
            "command": "uv run {hooks_path}"
          }}
        ]
      }}
    ],
    "PostToolUse": [
      {{
        "matcher": "*",
        "hooks": [
          {{
            "type": "command",
            "command": "uv run {hooks_path}"
          }}
        ]
      }}
    ],
    "Stop": [
      {{
        "hooks": [
          {{
            "type": "command",
            "command": "uv run {hooks_path}"
          }}
        ]
      }}
    ]
  }}
}}
'''


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        print("[green]fasthooks[/green] version: [bold]0.1.0[/bold]")
        raise typer.Exit()


@app.callback()
def callback(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-v",
            help="Show the version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """
    [bold]fasthooks[/bold] - Delightful Claude Code hooks 🪝

    Build hooks for Claude Code with a FastAPI-like developer experience.

    Read more: [link=https://github.com/oneryalcin/fasthooks]https://github.com/oneryalcin/fasthooks[/link]
    """
    pass


@app.command()
def init(
    path: Annotated[
        Path,
        typer.Argument(
            help="Directory to create for the hooks project (e.g., ./my-hooks)"
        ),
    ],
) -> None:
    """
    Initialize a new hooks project. 🚀

    Creates a new directory with starter hooks.py and pyproject.toml files.

    Example:

        $ fasthooks init my-hooks

        $ cd my-hooks && uv sync
    """
    # Check if directory exists and has files
    if path.exists():
        existing_files = list(path.iterdir())
        if existing_files:
            print(f"[red]Error:[/red] Directory [bold]{path}[/bold] already exists and not empty")
            raise typer.Exit(code=1)

    # Create directory
    path.mkdir(parents=True, exist_ok=True)

    # Write hooks.py
    hooks_file = path / "hooks.py"
    hooks_file.write_text(HOOKS_TEMPLATE)

    # Write pyproject.toml
    pyproject_file = path / "pyproject.toml"
    project_name = path.name.replace("-", "_").replace(" ", "_")
    pyproject_file.write_text(PYPROJECT_TEMPLATE.format(name=project_name))

    # Write .claude/settings.json
    claude_dir = path / ".claude"
    claude_dir.mkdir(exist_ok=True)
    settings_file = claude_dir / "settings.json"
    hooks_path = path.absolute() / "hooks.py"
    settings_file.write_text(SETTINGS_TEMPLATE.format(hooks_path=hooks_path))

    print()
    print(f"[green]✓[/green] Created hooks project at [bold]{path}[/bold]")
    print()
    print("[bold]Files created:[/bold]")
    print(f"  {path}/hooks.py              - Your hook handlers")
    print(f"  {path}/pyproject.toml        - Project dependencies")
    print(f"  {path}/.claude/settings.json - Claude Code config")
    print()
    print("[bold]Next steps:[/bold]")
    print(f"  cd {path}")
    print("  # Edit hooks.py to add your hooks")
    print("  # Copy .claude/settings.json to your target project")


@app.command()
def run(
    path: Annotated[
        Path | None,
        typer.Argument(
            help="Path to hooks.py file (default: ./hooks.py)"
        ),
    ] = None,
    input_file: Annotated[
        Path | None,
        typer.Option(
            "--input", "-i",
            help="JSON file to use as input instead of stdin (for testing)"
        ),
    ] = None,
) -> None:
    """
    Run hooks in stdin/stdout mode. 📥

    This command is typically called by Claude Code via settings.json.

    For local testing, use --input to provide a JSON file:

        $ fasthooks run hooks.py --input test_event.json

    Your hooks.py should contain:

        from fasthooks import HookApp

        app = HookApp()

        @app.pre_tool("Bash")
        def check(event):
            ...

        app.run()

    Then configure in settings.json:

        "hooks": {"PreToolUse": [{"command": "python hooks.py"}]}
    """
    if path is None:
        path = Path("hooks.py")

    if not path.exists():
        print(f"[red]Error:[/red] File [bold]{path}[/bold] not found")
        print()
        print("Create a hooks project with: [bold]fasthooks init my-hooks[/bold]")
        raise typer.Exit(code=1)

    # If --input provided, redirect stdin from file
    if input_file is not None:
        if not input_file.exists():
            print(f"[red]Error:[/red] Input file [bold]{input_file}[/bold] not found")
            raise typer.Exit(code=1)
        sys.stdin = input_file.open("r")

    # Execute the hooks file
    import runpy
    sys.argv = [str(path)]
    runpy.run_path(str(path), run_name="__main__")


def main() -> None:
    """CLI entry point."""
    app()


if __name__ == "__main__":
    main()
