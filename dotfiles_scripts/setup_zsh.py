#!/usr/bin/env python3
"""Setup zsh as default shell with antidote plugin manager."""

from __future__ import annotations

import getpass
import os
import shutil
import subprocess
import sys
from pathlib import Path

from dotfiles_scripts.setup_utils import (
    is_linux,
    print_header,
    print_step,
    print_success,
    print_warning,
)


def is_zsh_default() -> bool:
    """Check if zsh is the default shell."""
    shell = os.environ.get("SHELL", "")
    return "zsh" in shell


def ensure_zsh_installed() -> str | None:
    """Return the path to zsh, installing it via apt on Linux if missing."""
    zsh_path = shutil.which("zsh")
    if zsh_path:
        return zsh_path

    if is_linux() and shutil.which("apt-get"):
        print_step("zsh not found — installing via apt...")
        try:
            subprocess.run(["sudo", "apt-get", "update", "-qq"], check=True, stdin=subprocess.DEVNULL)
            subprocess.run(["sudo", "apt-get", "install", "-y", "zsh"], check=True, stdin=subprocess.DEVNULL)
        except subprocess.CalledProcessError as e:
            print_warning(f"Failed to install zsh: {e}")
            return None
        return shutil.which("zsh")

    return None


def set_zsh_default(zsh_path: str) -> bool:
    """Set zsh as the default shell."""
    print_step(f"Setting {zsh_path} as default shell...")

    # Add to /etc/shells if not present
    try:
        with Path("/etc/shells").open() as f:
            shells = f.read()

        if zsh_path not in shells:
            print_step(f"Adding {zsh_path} to /etc/shells...")
            subprocess.run(
                ["sudo", "sh", "-c", f"echo {zsh_path} >> /etc/shells"],
                check=True,
                stdin=subprocess.DEVNULL,
            )
    except Exception as e:
        print_warning(f"Could not update /etc/shells: {e}")

    # Change shell. On Linux `chsh` prompts for the user's password, which
    # hangs in a non-interactive run — go through sudo (targeting the user)
    # instead. On macOS the interactive `chsh` is the expected path.
    try:
        if is_linux():
            subprocess.run(
                ["sudo", "chsh", "-s", zsh_path, getpass.getuser()],
                check=True,
                stdin=subprocess.DEVNULL,
            )
        else:
            subprocess.run(["chsh", "-s", zsh_path], check=True)
        print_success(f"Default shell set to {zsh_path}")
        return True
    except subprocess.CalledProcessError as e:
        print_warning(f"Failed to change shell: {e}")
        return False


def main() -> int:
    """Main entry point."""
    print_header("Setting up zsh")

    zsh_path = ensure_zsh_installed()
    if not zsh_path:
        print_warning("zsh not available — skipping default-shell setup")
        return 0

    if is_zsh_default():
        print_success("zsh is already the default shell")
    else:
        set_zsh_default(zsh_path)

    print_success("zsh setup complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
