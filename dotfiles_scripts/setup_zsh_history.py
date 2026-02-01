#!/usr/bin/env python3
"""Setup shared zsh history via Dropbox."""

from __future__ import annotations

import sys
from pathlib import Path

from dotfiles_scripts.setup_device_id import ensure_device_id
from dotfiles_scripts.setup_utils import (
    DROPBOX_DIR,
    print_header,
    print_step,
    print_success,
    print_warning,
)


def get_device_history_file(device_id: str) -> Path:
    """Get the path to the device-specific zsh history file."""
    return DROPBOX_DIR / "dotfiles" / "zsh_history" / f".zsh_history.{device_id}"


def main() -> int:
    """Main entry point."""
    print_header("Setting up zsh history")

    # Check Dropbox
    dropbox_dotfiles = DROPBOX_DIR / "dotfiles"
    if not dropbox_dotfiles.exists():
        print_warning("Dropbox dotfiles not found, skipping zsh history setup")
        return 0

    # Get or create device ID
    device_id = ensure_device_id()
    if not device_id:
        return 0

    # Ensure zsh_history directory exists
    zsh_history_dir = DROPBOX_DIR / "dotfiles" / "zsh_history"
    zsh_history_dir.mkdir(parents=True, exist_ok=True)

    # Get device-specific history file
    device_history = get_device_history_file(device_id)

    # Create if doesn't exist
    if not device_history.exists():
        local_history = Path.home() / ".zsh_history"

        if local_history.exists() and not local_history.is_symlink():
            print_step(f"Copying existing history to {device_history}")
            device_history.write_bytes(local_history.read_bytes())
        else:
            print_step(f"Creating {device_history}")
            device_history.touch()

    print_success(f"HISTFILE will use: {device_history}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
