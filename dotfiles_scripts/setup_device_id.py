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
# Allows: mac, macbook-pro, mac.personal, macbook-pro.work
# Each segment must start with letter, can contain lowercase letters, numbers, hyphens
DEVICE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)*$")
MACHINE_CONFIG_DIR = DROPBOX_DIR / "dotfiles" / "home" / ".config" / "dotfiles"


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

    device_ids: list[str] = []
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
            device_id = input("  Enter device name (e.g. macbook-pro, mac.personal): ").strip()
            if not device_id:
                print_warning("No device ID provided, skipping device-specific setup")
                return None

            if is_valid_device_id(device_id):
                break

            print_warning(
                "Invalid format. Use lowercase letters, numbers, hyphens, dots. "
                "Start each segment with a letter."
            )

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


def get_hierarchy_levels(device_id: str) -> list[str]:
    """Get all hierarchy levels for a device ID.

    For 'mac.personal' returns: ['', 'mac', 'mac.personal']
    The empty string represents the base config.
    """
    segments = device_id.split(".")
    levels = [""]  # base config
    prefix = ""
    for segment in segments:
        prefix = f"{prefix}.{segment}" if prefix else segment
        levels.append(prefix)
    return levels


def setup_machine_config(device_id: str) -> bool:
    """Setup machine-specific config files for all hierarchy levels.

    Files are created in ~/Dropbox/dotfiles/home/.config/dotfiles/ and
    automatically symlinked to ~/.config/dotfiles/ by setup_dropbox.
    """
    # Create config directory if needed
    if not MACHINE_CONFIG_DIR.exists():
        MACHINE_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        print_step(f"Created {MACHINE_CONFIG_DIR}")

    levels = get_hierarchy_levels(device_id)

    for level in levels:
        # Determine file name
        suffix = f".{level}" if level else ""
        config_file = MACHINE_CONFIG_DIR / f".dotfiles-config{suffix}"

        # Create config file with template if it doesn't exist
        if not config_file.exists():
            if level:
                template = f"""# Machine-specific configuration for {level}
# This file is sourced by ~/.zshrc
# Add environment variables and settings specific to this machine level

# Example settings:
# export ENABLE_ZPROF=yes        # Enable zsh startup profiling
# export ANTIGEN_BUNDLE_NODE=y   # Enable Node.js completion bundles
"""
            else:
                template = """# Base dotfiles configuration (shared across all devices)
# This file is sourced by ~/.zshrc before device-specific configs

# Example settings:
# export ENABLE_ZPROF=yes        # Enable zsh startup profiling
# export ANTIGEN_BUNDLE_NODE=y   # Enable Node.js completion bundles
"""
            config_file.write_text(template)
            print_success(f"Created {config_file}")
        else:
            print_step(f"Exists: {config_file.name}")

    return True


def main() -> int:
    """Main entry point."""
    print_header("Setting up device ID")

    device_id = get_device_id()
    if not device_id:
        device_id = setup_device_id_interactive()
        if not device_id:
            return 1

    print_success(f"Device ID: {device_id}")

    # Setup machine config if Dropbox is available
    if DROPBOX_DIR.exists():
        setup_machine_config(device_id)
    else:
        print_warning("Dropbox not found - skipping machine config setup")

    return 0


if __name__ == "__main__":
    sys.exit(main())
