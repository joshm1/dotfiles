"""Common utilities for dotfiles scripts."""

import os
from datetime import datetime, timezone
from pathlib import Path


def utctz() -> timezone:
    """Return the UTC timezone."""
    return timezone.utc


def utcnow() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(tz=utctz())


def get_dotfiles_dir() -> Path:
    """Get the dotfiles directory path from environment or default."""
    dotfiles = os.environ.get("DOTFILES", str(Path.home() / ".dotfiles"))
    return Path(dotfiles)


def get_backup_dir() -> Path:
    """Get a timestamped backup directory path."""
    timestamp = utcnow().strftime("%Y%m%d-%H%M%S")
    return Path.home() / f".dotfiles.{timestamp}.bck"
