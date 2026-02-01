#!/usr/bin/env python3
"""
Main setup script for dotfiles.

This script uses only the standard library so it can run with system Python (3.9+).
It orchestrates the setup of all dotfiles components.
"""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

# Add parent directory to path so we can import sibling modules
# when running directly with system Python
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from dotfiles_scripts.setup_utils import (
    DOTFILES,
    DOTFILES_REPO,
    DROPBOX_DIR,
    create_symlink,
    get_backup_dir,
    print_error,
    print_header,
    print_success,
    print_warning,
    run_cmd,
)


def is_mac() -> bool:
    return platform.system() == "Darwin"


def is_wsl() -> bool:
    try:
        with open("/proc/version", "r") as f:
            return "microsoft" in f.read().lower()
    except FileNotFoundError:
        return False


def setup_git_submodules() -> bool:
    """Initialize and update git submodules."""
    print_header("Git submodules")
    try:
        run_cmd(["git", "submodule", "update", "--init"], cwd=DOTFILES_REPO)
        return True
    except Exception:
        return False


def setup_dotfiles_symlink() -> bool:
    """Create the ~/.dotfiles symlink to the repo."""
    print_header("Dotfiles symlink")
    return create_symlink(DOTFILES_REPO, DOTFILES)


def setup_config_dir() -> bool:
    """Ensure ~/.config directory exists."""
    config_dir = Path.home() / ".config"
    config_dir.mkdir(exist_ok=True)
    print_success(f"Ensured {config_dir} exists")
    return True


def symlink_home_files() -> bool:
    """Symlink all files from home/ directory to $HOME."""
    print_header("Symlinking home files")

    home_dir = DOTFILES_REPO / "home"
    if not home_dir.exists():
        print_error(f"home/ directory not found at {home_dir}")
        return False

    backup_dir = get_backup_dir()
    success = True

    # Symlink top-level files
    for source_path in sorted(home_dir.glob("*")):
        if source_path.is_file():
            target_path = Path.home() / source_path.name
            if not create_symlink(source_path, target_path, backup_dir):
                success = False

    # Symlink .config subdirectories
    config_dir = home_dir / ".config"
    if config_dir.exists():
        for source_path in sorted(config_dir.glob("*")):
            target_path = Path.home() / ".config" / source_path.name
            if not create_symlink(source_path, target_path, backup_dir):
                success = False

    return success


def run_setup_module(module_name: str) -> bool:
    """Run a setup module."""
    try:
        module = __import__(f"dotfiles_scripts.{module_name}", fromlist=["main"])
        return module.main() == 0
    except Exception as e:
        print_error(f"Failed to run {module_name}: {e}")
        return False


def cli() -> int:
    """CLI entry point."""
    print_header("Dotfiles Setup")
    print(f"Repository: {DOTFILES_REPO}")
    print(f"Target:     {DOTFILES}")
    print(f"Platform:   {'macOS' if is_mac() else 'WSL' if is_wsl() else 'Linux'}")
    print(f"Python:     {sys.version}")

    os.chdir(DOTFILES_REPO)

    # Phase 1: Basic setup (no dependencies)
    steps = [
        ("Git submodules", setup_git_submodules),
        ("Dotfiles symlink", setup_dotfiles_symlink),
        ("Config directory", setup_config_dir),
    ]

    for name, func in steps:
        if not func():
            print_error(f"Failed: {name}")
            return 1

    # Phase 2: Device ID (needed for device-specific Homebrew casks)
    run_setup_module("setup_device_id")

    # Phase 3: macOS defaults
    run_setup_module("setup_macos")

    # Phase 4: Homebrew (uses device_id for device-specific Dropbox Brewfiles)
    if not run_setup_module("setup_homebrew"):
        print_error("Homebrew setup failed")
        return 1

    # Phase 5: Neovim nightly (install early as a core editor)
    run_setup_module("setup_neovim")

    # Phase 6: mise (version manager)
    run_setup_module("setup_mise")

    # Phase 7: Shell setup
    run_setup_module("setup_zsh")

    # Phase 8: Neovim config
    run_setup_module("setup_vim")

    # Phase 9: Symlink home files
    symlink_home_files()

    # Phase 10: fzf
    run_setup_module("setup_fzf")

    # Phase 11: Dropbox-dependent setup (optional)
    if DROPBOX_DIR.exists():
        run_setup_module("setup_dropbox")
        run_setup_module("setup_zsh_history")
    else:
        print_warning("Dropbox not found - skipping Dropbox-dependent setup")
        print("  Run setup-dropbox and setup-zsh-history later after setting up Dropbox")

    print_header("Setup Complete!")
    print("Language runtimes (Python, Node, Ruby) are managed by mise.")
    print("Run 'mise doctor' to verify your setup.")

    return 0


if __name__ == "__main__":
    sys.exit(cli())
