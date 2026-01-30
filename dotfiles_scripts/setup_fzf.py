#!/usr/bin/env python3
"""Setup fzf keybindings and completion."""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

from dotfiles_scripts.setup_utils import (
    print_header,
    print_step,
    print_success,
    print_warning,
)


def is_mac() -> bool:
    return platform.system() == "Darwin"


def main() -> int:
    """Main entry point."""
    print_header("Setting up fzf")

    fzf_zsh = Path.home() / ".fzf.zsh"
    if fzf_zsh.exists():
        print_success("fzf already configured")
        return 0

    # Find fzf install script
    fzf_install_paths = [
        Path("/opt/homebrew/opt/fzf/install"),  # macOS ARM
        Path("/usr/local/opt/fzf/install"),      # macOS Intel
        Path.home() / ".fzf" / "install",        # Git install
    ]

    fzf_install = None
    for path in fzf_install_paths:
        if path.exists():
            fzf_install = path
            break

    if not fzf_install:
        print_warning("fzf install script not found")
        print("  Install fzf first: brew install fzf")
        return 0

    print_step(f"Running fzf install from {fzf_install}...")

    try:
        subprocess.run(
            [str(fzf_install), "--all", "--no-bash", "--no-fish"],
            check=True,
        )
        print_success("fzf configured")
    except subprocess.CalledProcessError as e:
        print_warning(f"fzf install failed: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
