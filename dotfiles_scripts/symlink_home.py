#!/usr/bin/env python3
"""
Automatically symlink files from $DOTFILES/home/ to $HOME.

This script discovers all files in the home/ directory and creates
symlinks to their corresponding locations in $HOME, backing up any
existing files.
"""

import sys
from pathlib import Path

import click
from rich.console import Console

from dotfiles_scripts.utils import get_backup_dir, get_dotfiles_dir

console = Console()


def create_symlink(
    source: Path, target: Path, backup_dir: Path, dry_run: bool = False
) -> tuple[bool, str]:
    """
    Create a symlink from source to target.

    Args:
        source: Path to the source file/directory
        target: Path where the symlink should be created
        backup_dir: Directory to backup existing files to
        dry_run: If True, only show what would be done without making changes

    Returns:
        (success, message) tuple
    """
    # Check if target already exists and is the correct symlink
    if target.is_symlink() and target.resolve() == source.resolve():
        return True, f"[dim]{target} already links to {source}[/dim]"

    # Backup existing file/directory if it exists
    if target.exists() or target.is_symlink():
        backup_path = backup_dir / target.name
        if dry_run:
            console.print(f"[yellow][DRY RUN] Would backup {target} → {backup_path}[/yellow]")
        else:
            backup_dir.mkdir(parents=True, exist_ok=True)
            try:
                target.rename(backup_path)
                console.print(f"[yellow]Backed up {target} → {backup_path}[/yellow]")
            except Exception as e:
                return False, f"[red]Failed to backup {target}: {e}[/red]"

    # Create the symlink
    if dry_run:
        return True, f"[cyan][DRY RUN][/cyan] Would link {target} → {source}"
    else:
        # Create parent directory if needed
        target.parent.mkdir(parents=True, exist_ok=True)

        try:
            target.symlink_to(source)
            return True, f"[green]✓[/green] {target} → {source}"
        except Exception as e:
            return False, f"[red]✗ Failed to link {target}: {e}[/red]"


def symlink_home_files(dry_run: bool = False) -> int:
    """
    Main function to symlink all files from home/ to $HOME.

    Args:
        dry_run: If True, only show what would be done without making changes

    Returns:
        Exit code (0 for success, 1 for errors)
    """
    dotfiles = get_dotfiles_dir()
    home_dir = dotfiles / "home"

    if not home_dir.exists():
        console.print(f"[red]Error: {home_dir} does not exist![/red]")
        return 1

    if dry_run:
        console.print("[bold cyan]DRY RUN MODE[/bold cyan] - No changes will be made\n")

    console.print(f"[bold]Auto-discovering files in {home_dir}...[/bold]\n")

    backup_dir = get_backup_dir()
    results: list[str] = []
    errors: list[str] = []

    # Symlink all top-level files in home/
    for source_path in sorted(home_dir.glob("*")):
        if source_path.is_file():
            target_path = Path.home() / source_path.name
            success, message = create_symlink(source_path, target_path, backup_dir, dry_run)
            results.append(message)
            if not success:
                errors.append(message)

    # Symlink .config subdirectories
    config_dir = home_dir / ".config"
    if config_dir.exists():
        for source_path in sorted(config_dir.glob("*")):
            target_path = Path.home() / ".config" / source_path.name
            success, message = create_symlink(source_path, target_path, backup_dir, dry_run)
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
        if dry_run:
            console.print("[bold cyan]✓ Dry run complete - no changes made[/bold cyan]")
        else:
            console.print("[bold green]✓ All home files symlinked successfully![/bold green]")
        return 0


@click.command()
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be done without making any changes",
)
def cli(dry_run: bool) -> None:
    """CLI entry point."""
    sys.exit(symlink_home_files(dry_run))


if __name__ == "__main__":
    cli()
