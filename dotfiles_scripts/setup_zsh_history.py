#!/usr/bin/env python3
"""Setup shared zsh history under ``~/.dotfiles-private/zsh_history/``.

The cloud-storage indirection lives in ``~/.dotfiles-private``: this script
just reads/writes through that single canonical path.
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotfiles_scripts.setup_device_id import ensure_device_id
from dotfiles_scripts.setup_utils import (
    PRIVATE_DOTFILES,
    get_private_dotfiles,
    print_header,
    print_step,
    print_success,
    print_warning,
)


def get_device_history_file(device_id: str) -> Path:
    """Path to this device's zsh history file under ``~/.dotfiles-private``.

    Returns the path even if the underlying symlink is missing — callers are
    expected to gate on ``get_private_dotfiles()`` first when that matters.
    """
    return PRIVATE_DOTFILES / "zsh_history" / f".zsh_history.{device_id}"


def main() -> int:
    """Main entry point."""
    print_header("Setting up zsh history")

    private = get_private_dotfiles()
    if private is None:
        print_warning(
            "~/.dotfiles-private is not set up; skipping zsh history setup"
        )
        return 0

    device_id = ensure_device_id()
    if not device_id:
        return 0

    zsh_history_dir = private / "zsh_history"
    zsh_history_dir.mkdir(parents=True, exist_ok=True)

    device_history = zsh_history_dir / f".zsh_history.{device_id}"

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
