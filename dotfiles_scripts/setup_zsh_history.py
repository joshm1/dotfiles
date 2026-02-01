#!/usr/bin/env python3
"""Setup shared zsh history via Dropbox."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from dotfiles_scripts.setup_utils import (
    DROPBOX_DIR,
    print_header,
    print_step,
    print_success,
    print_warning,
)


DEVICE_ID_FILE = Path.home() / ".device_id"
DEVICE_ID_PATTERN = re.compile(r"^[a-z]([a-z0-9-]*[a-z0-9])?$")


def is_valid_device_id(device_id: str) -> bool:
    """Check if device ID is valid (lowercase, dash-case, starts with letter)."""
    return bool(DEVICE_ID_PATTERN.match(device_id))


def get_device_id() -> str | None:
    """Get the device ID, or prompt user to create one."""
    if DEVICE_ID_FILE.exists():
        return DEVICE_ID_FILE.read_text().strip()
    return None


def get_known_device_ids() -> list[str]:
    """Get list of known device IDs from existing history files."""
    zsh_history_dir = DROPBOX_DIR / "dotfiles" / "zsh_history"
    if not zsh_history_dir.exists():
        return []

    device_ids = []
    for f in zsh_history_dir.iterdir():
        if f.name.startswith(".zsh_history."):
            device_id = f.name.removeprefix(".zsh_history.")
            if device_id:
                device_ids.append(device_id)
    return sorted(device_ids)


def setup_device_id() -> str | None:
    """Setup device ID interactively."""
    print_step("No device ID found")
    print("  A device ID is used to maintain separate zsh history files per machine.")

    known_ids = get_known_device_ids()
    if known_ids:
        print(f"  Known devices: {', '.join(known_ids)}")

    try:
        while True:
            device_id = input("  Enter device name (e.g. macbook-pro): ").strip()
            if not device_id:
                print_warning("No device ID provided, skipping zsh history setup")
                return None

            if is_valid_device_id(device_id):
                break

            print_warning("Invalid format. Use lowercase, dash-case, starting with a letter.")

        DEVICE_ID_FILE.write_text(device_id)
        print_success(f"Device ID set to: {device_id}")
        return device_id

    except (EOFError, KeyboardInterrupt):
        print()
        print_warning("Skipping device ID setup")
        return None


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
    device_id = get_device_id()
    if not device_id:
        device_id = setup_device_id()
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
