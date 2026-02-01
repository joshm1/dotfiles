#!/usr/bin/env python3
"""Setup zsh as default shell with antigen plugin manager."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from dotfiles_scripts.setup_utils import (
    DOTFILES_REPO,
    create_symlink,
    print_header,
    print_step,
    print_success,
    print_warning,
)


def is_zsh_default() -> bool:
    """Check if zsh is the default shell."""
    shell = os.environ.get("SHELL", "")
    return "zsh" in shell


def set_zsh_default() -> bool:
    """Set zsh as the default shell."""
    zsh_path = shutil.which("zsh")
    if not zsh_path:
        print_warning("zsh not found")
        return False

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
            )
    except Exception as e:
        print_warning(f"Could not update /etc/shells: {e}")

    # Change shell
    try:
        subprocess.run(["chsh", "-s", zsh_path], check=True)
        print_success(f"Default shell set to {zsh_path}")
        return True
    except subprocess.CalledProcessError as e:
        print_warning(f"Failed to change shell: {e}")
        return False


def setup_antigen() -> bool:
    """Setup antigen zsh plugin manager."""
    antigen_src = DOTFILES_REPO / "zsh" / "antigen.zsh"
    antigen_target = Path.home() / ".antigen.zsh"

    if antigen_src.exists():
        create_symlink(antigen_src, antigen_target)
        return True
    else:
        print_warning(f"antigen.zsh not found at {antigen_src}")
        return False


def main() -> int:
    """Main entry point."""
    print_header("Setting up zsh")

    if is_zsh_default():
        print_success("zsh is already the default shell")
    else:
        set_zsh_default()

    setup_antigen()

    print_success("zsh setup complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
