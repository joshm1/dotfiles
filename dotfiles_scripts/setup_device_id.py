#!/usr/bin/env python3
"""Setup device ID for machine-specific configuration."""

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
    """Get the device ID from ~/.device_id file."""
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


def setup_device_id_interactive() -> str | None:
    """Setup device ID interactively."""
    print_step("No device ID found")
    print("  A device ID identifies this machine for device-specific configuration.")

    known_ids = get_known_device_ids()
    if known_ids:
        print(f"  Known devices: {', '.join(known_ids)}")

    try:
        while True:
            device_id = input("  Enter device name (e.g. macbook-pro): ").strip()
            if not device_id:
                print_warning("No device ID provided, skipping device-specific setup")
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


def ensure_device_id() -> str | None:
    """Get existing device ID or prompt to create one."""
    device_id = get_device_id()
    if device_id:
        return device_id
    return setup_device_id_interactive()


def main() -> int:
    """Main entry point."""
    print_header("Setting up device ID")

    device_id = get_device_id()
    if device_id:
        print_success(f"Device ID: {device_id}")
        return 0

    device_id = setup_device_id_interactive()
    return 0 if device_id else 1


if __name__ == "__main__":
    sys.exit(main())
