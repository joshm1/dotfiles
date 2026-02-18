#!/usr/bin/env python3
"""
Automatically symlink files from $DOTFILES/home/ to $HOME.

Uses the shared symlink_home_dir function which supports .symlink-dir tags:
directories containing a .symlink-dir file are symlinked as a whole,
otherwise the function recurses into them and symlinks children individually.
"""

import sys

import click

from dotfiles_scripts.setup_utils import symlink_home_dir
from dotfiles_scripts.utils import get_dotfiles_dir


@click.command()
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be done without making any changes",
)
def cli(dry_run: bool) -> None:
    """Symlink all files from home/ to $HOME."""
    dotfiles = get_dotfiles_dir()
    home_dir = dotfiles / "home"

    if not home_dir.exists():
        click.echo(f"Error: {home_dir} does not exist!", err=True)
        sys.exit(1)

    if dry_run:
        click.echo("DRY RUN MODE - showing what would be done (not yet supported, running normally)\n")

    symlink_home_dir(home_dir)


if __name__ == "__main__":
    cli()
