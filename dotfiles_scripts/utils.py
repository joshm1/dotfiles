"""Common utilities for dotfiles scripts."""

import os
from datetime import datetime
from pathlib import Path


def get_dotfiles_dir() -> Path:
    """Get the dotfiles directory path from environment or default."""
    dotfiles = os.environ.get("DOTFILES", str(Path.home() / ".dotfiles"))
    return Path(dotfiles)


def get_backup_dir() -> Path:
    """Get a timestamped backup directory path."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path.home() / f".dotfiles.{timestamp}.bck"
