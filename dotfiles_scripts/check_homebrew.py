"""
Check which apps in /Applications are available in Homebrew but not installed via Homebrew.

Usage: uv run check-homebrew-apps
"""

import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.panel import Panel


console = Console()


def get_installed_casks():
    """Get list of currently installed Homebrew casks."""
    try:
        result = subprocess.run(
            ["brew", "list", "--cask"],
            capture_output=True,
            text=True,
            check=True,
        )
        return set(result.stdout.strip().split("\n"))
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error getting installed casks: {e}[/red]")
        return set()


def get_applications():
    """Get list of all applications in /Applications."""
    apps_dir = Path("/Applications")
    if not apps_dir.exists():
        console.print("[red]/Applications directory not found[/red]")
        return []

    apps = []
    for item in apps_dir.iterdir():
        if item.suffix == ".app":
            apps.append(item.stem)
    return sorted(apps)


def normalize_name(name):
    """Normalize app name for Homebrew comparison."""
    # Convert to lowercase and replace spaces with hyphens
    return name.lower().replace(" ", "-").replace(".", "")


def is_available_in_homebrew(app_name):
    """Check if an app is available as a Homebrew cask."""
    normalized = normalize_name(app_name)

    try:
        result = subprocess.run(
            ["brew", "search", "--cask", f"^{normalized}$"],
            capture_output=True,
            text=True,
            check=False,
        )

        # Check if the exact name appears in the output
        if result.returncode == 0 and normalized in result.stdout.lower():
            return True

        # Also try searching for the original name
        result = subprocess.run(
            ["brew", "search", "--cask", app_name],
            capture_output=True,
            text=True,
            check=False,
        )

        return result.returncode == 0 and len(result.stdout.strip()) > 0

    except Exception as e:
        console.print(f"[red]Error checking {app_name}: {e}[/red]")
        return False


@click.command()
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed checking progress",
)
@click.option(
    "--output-format",
    "-f",
    type=click.Choice(["table", "list", "brewfile"], case_sensitive=False),
    default="table",
    help="Output format: table, list, or brewfile",
)
def cli(verbose, output_format):
    """Check which apps in /Applications are available in Homebrew but not installed via Homebrew."""

    console.print(
        Panel.fit(
            "[bold cyan]Homebrew Apps Checker[/bold cyan]\n"
            "Finding apps available in Homebrew but not installed via Homebrew",
            border_style="cyan",
        )
    )

    # Get installed casks
    installed_casks = get_installed_casks()
    console.print(f"\n[green]✓[/green] Found {len(installed_casks)} apps installed via Homebrew")

    # Get all applications
    all_apps = get_applications()
    console.print(f"[green]✓[/green] Found {len(all_apps)} total apps in /Applications\n")

    # Check each app
    available_not_installed = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Checking apps...", total=len(all_apps))

        for i, app in enumerate(all_apps, 1):
            normalized = normalize_name(app)

            # Update progress description to show current app
            progress.update(task, description=f"[cyan]Checking {i}/{len(all_apps)}: {app}...")

            # Skip if already installed via Homebrew
            if normalized in installed_casks or any(
                normalized == normalize_name(cask) for cask in installed_casks
            ):
                if verbose:
                    progress.stop()
                    console.print(f"  [dim]Skipping {app} (installed via Homebrew)[/dim]")
                    progress.start()
                progress.advance(task)
                continue

            # Check if available in Homebrew
            is_available = is_available_in_homebrew(app)

            if verbose:
                progress.stop()
                if is_available:
                    console.print(f"  [cyan]{app}[/cyan] [green]✓ Available[/green]")
                else:
                    console.print(f"  [cyan]{app}[/cyan] [dim]✗ Not found[/dim]")
                progress.start()

            if is_available:
                available_not_installed.append(app)

            progress.advance(task)

    # Print results
    console.print()
    console.print(
        Panel.fit(
            f"[bold green]{len(available_not_installed)}[/bold green] apps available in Homebrew "
            f"but NOT installed via Homebrew",
            border_style="green",
        )
    )
    console.print()

    if not available_not_installed:
        console.print("[green]All apps are either installed via Homebrew or not available as casks![/green]")
        return 0

    if output_format == "table":
        table = Table(title="Apps Available in Homebrew", show_lines=True)
        table.add_column("App Name", style="cyan", no_wrap=False)
        table.add_column("Homebrew Cask Name", style="yellow")

        for app in available_not_installed:
            table.add_row(app, normalize_name(app))

        console.print(table)

    elif output_format == "list":
        for app in available_not_installed:
            console.print(f"  • [cyan]{app}[/cyan]")

    elif output_format == "brewfile":
        console.print("[bold]Add to homebrew/Brewfile-casks:[/bold]\n")
        for app in available_not_installed:
            console.print(f'cask "{normalize_name(app)}"')

    return 0


if __name__ == "__main__":
    sys.exit(cli())
