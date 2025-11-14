#!/usr/bin/env python3
"""
Automatically symlink files from $DOTFILES/home/ to $HOME.

This script discovers all files in the home/ directory and creates
symlinks to their corresponding locations in $HOME, backing up any
existing files.
"""

import sys
from pathlib import Path
from rich.console import Console

from dotfiles_scripts.utils import get_dotfiles_dir, get_backup_dir

console = Console()


def create_symlink(source: Path, target: Path, backup_dir: Path) -> tuple[bool, str]:
    """
    Create a symlink from source to target.

    Args:
        source: Path to the source file/directory
        target: Path where the symlink should be created
        backup_dir: Directory to backup existing files to

    Returns:
        (success, message) tuple
    """
    # Check if target already exists and is the correct symlink
    if target.is_symlink() and target.resolve() == source.resolve():
        return True, f"[dim]{target} already links to {source}[/dim]"

    # Backup existing file/directory if it exists
    if target.exists() or target.is_symlink():
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / target.name
        try:
            target.rename(backup_path)
            console.print(f"[yellow]Backed up {target} → {backup_path}[/yellow]")
        except Exception as e:
            return False, f"[red]Failed to backup {target}: {e}[/red]"

    # Create parent directory if needed
    target.parent.mkdir(parents=True, exist_ok=True)

    # Create the symlink
    try:
        target.symlink_to(source)
        return True, f"[green]✓[/green] {target} → {source}"
    except Exception as e:
        return False, f"[red]✗ Failed to link {target}: {e}[/red]"


def symlink_home_files() -> int:
    """
    Main function to symlink all files from home/ to $HOME.

    Returns:
        Exit code (0 for success, 1 for errors)
    """
    dotfiles = get_dotfiles_dir()
    home_dir = dotfiles / "home"

    if not home_dir.exists():
        console.print(f"[red]Error: {home_dir} does not exist![/red]")
        return 1

    console.print(f"[bold]Auto-discovering files in {home_dir}...[/bold]\n")

    backup_dir = get_backup_dir()
    results = []
    errors = []

    # Symlink all top-level files in home/
    for source_path in sorted(home_dir.glob("*")):
        if source_path.is_file():
            target_path = Path.home() / source_path.name
            success, message = create_symlink(source_path, target_path, backup_dir)
            results.append(message)
            if not success:
                errors.append(message)

    # Symlink .config subdirectories
    config_dir = home_dir / ".config"
    if config_dir.exists():
        for source_path in sorted(config_dir.glob("*")):
            target_path = Path.home() / ".config" / source_path.name
            success, message = create_symlink(source_path, target_path, backup_dir)
            results.append(message)
            if not success:
                errors.append(message)

    # Print results
    console.print()
    for result in results:
        console.print(result)

    console.print()
    if errors:
        console.print(f"[red]Completed with {len(errors)} error(s)[/red]")
        return 1
    else:
        console.print("[bold green]✓ All home files symlinked successfully![/bold green]")
        return 0


def main():
    """Entry point for the CLI command."""
    sys.exit(symlink_home_files())


if __name__ == "__main__":
    main()
