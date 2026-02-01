"""Shared utilities for setup scripts."""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Configuration
DOTFILES_REPO = Path.home() / "projects" / "joshm1" / "dotfiles"
DOTFILES = Path.home() / ".dotfiles"
DROPBOX_DIR = Path.home() / "Dropbox"

# Backup directory (created lazily)
_backup_dir: Path | None = None


def get_backup_dir() -> Path:
    """Get a timestamped backup directory (created once per session)."""
    global _backup_dir
    if _backup_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        _backup_dir = Path.home() / f".dotfiles.{timestamp}.bck"
    return _backup_dir


def print_header(msg: str) -> None:
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}\n")


def print_step(msg: str) -> None:
    """Print a step message."""
    print(f"→ {msg}")


def print_success(msg: str) -> None:
    """Print a success message."""
    print(f"✓ {msg}")


def print_warning(msg: str) -> None:
    """Print a warning message."""
    print(f"⚠ {msg}")


def print_error(msg: str) -> None:
    """Print an error message."""
    print(f"✗ {msg}", file=sys.stderr)


def run_cmd(
    cmd: list[str] | str,
    check: bool = True,
    shell: bool = False,
    capture: bool = False,
    cwd: Path | None = None,
    quiet: bool = False,
    **kwargs,
) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    if capture:
        kwargs.setdefault("capture_output", True)
        kwargs.setdefault("text", True)
    if cwd:
        kwargs["cwd"] = cwd
    if not quiet:
        cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
        print_step(f"Running: {cmd_str}")
    return subprocess.run(cmd, check=check, shell=shell, **kwargs)


def create_symlink(source: Path, target: Path, backup_dir: Path | None = None) -> bool:
    """Create a symlink, backing up existing files if needed."""
    # Don't create broken symlinks
    if not source.exists():
        print_warning(f"Skipping {target.name}: source does not exist ({source})")
        return False

    # Already correct symlink?
    if target.is_symlink() and target.resolve() == source.resolve():
        print(f"  {target.name} already linked")
        return True

    # Backup existing file/directory
    if target.exists() or target.is_symlink():
        if backup_dir is None:
            backup_dir = get_backup_dir()
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / target.name
        print_warning(f"Backing up {target} → {backup_path}")
        target.rename(backup_path)

    # Create parent directory if needed
    target.parent.mkdir(parents=True, exist_ok=True)

    # Create symlink
    target.symlink_to(source)
    print_success(f"Linked {target} → {source}")
    return True
