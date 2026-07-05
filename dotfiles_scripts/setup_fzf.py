#!/usr/bin/env python3
"""Setup fzf keybindings and completion."""

from __future__ import annotations

import platform
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


def is_mac() -> bool:
    return platform.system() == "Darwin"


def clone_fzf() -> Path | None:
    """Clone fzf to ~/.fzf (shallow) and return its install script path.

    Fallback for platforms without a Homebrew-provided fzf (e.g. Linux
    servers). The upstream repo ships an ``install`` script that wires up
    the shell keybindings/completion the same way the brew formula does.
    """
    fzf_home = Path.home() / ".fzf"
    install = fzf_home / "install"
    if install.exists():
        return install
    if not shutil.which("git"):
        return None
    print_step("Cloning fzf to ~/.fzf ...")
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", "https://github.com/junegunn/fzf.git", str(fzf_home)],
            check=True,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as e:
        print_warning(f"Failed to clone fzf: {e}")
        return None
    return install if install.exists() else None


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

    if not fzf_install and is_linux():
        fzf_install = clone_fzf()

    if not fzf_install:
        print_warning("fzf install script not found")
        print("  Install fzf first: brew install fzf (or apt install fzf)")
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
