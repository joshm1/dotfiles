#!/usr/bin/env python3
"""Setup Dropbox-synced dotfiles by symlinking from ~/Dropbox/dotfiles/home/ to $HOME."""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

import yaml

from dotfiles_scripts.setup_utils import (
    DROPBOX_DIR,
    create_symlink,
    print_header,
    print_step,
    print_success,
    print_warning,
)

# Tag file that indicates a directory should be symlinked as a whole
SYMLINK_DIR_TAG = ".symlink-dir"

# Config file for directory-specific settings
DOTFILES_CONFIG = ".dotfiles.yaml"

# Files to skip when traversing
SKIP_FILES = {".DS_Store", SYMLINK_DIR_TAG, DOTFILES_CONFIG}


def is_mac() -> bool:
    return platform.system() == "Darwin"


def is_wsl() -> bool:
    try:
        with Path("/proc/version").open() as f:
            return "microsoft" in f.read().lower()
    except FileNotFoundError:
        return False


def setup_wsl_dropbox() -> None:
    """On WSL, create symlink to Windows Dropbox if needed."""
    if not is_wsl():
        return

    dropbox_link = Path.home() / "Dropbox"
    if dropbox_link.exists():
        return

    try:
        result = subprocess.run(
            ["cmd.exe", "/c", "echo %USERNAME%"],
            capture_output=True,
            text=True,
        )
        win_user = result.stdout.strip()
        win_dropbox = Path(f"/mnt/c/Users/{win_user}/Dropbox")

        if win_dropbox.is_dir():
            print_step("WSL detected: Creating symlink to Windows Dropbox...")
            dropbox_link.symlink_to(win_dropbox)
            print_success(f"Linked {dropbox_link} → {win_dropbox}")
        else:
            print_warning(f"Windows Dropbox not found at {win_dropbox}")
    except Exception as e:
        print_warning(f"Could not setup WSL Dropbox: {e}")


def symlink_home_dir(home_dir: Path) -> None:
    """
    Traverse home_dir and symlink everything to $HOME.

    If a directory contains .symlink-dir, symlink the directory itself.
    Otherwise, recurse into it and symlink children.
    """

    def process_dir(src_dir: Path, target_dir: Path) -> None:
        """Process a directory, symlinking contents or the dir itself."""
        for src in sorted(src_dir.iterdir()):
            if src.name in SKIP_FILES:
                continue

            target = target_dir / src.name

            if src.is_dir():
                # Check for .symlink-dir tag
                if (src / SYMLINK_DIR_TAG).exists():
                    # Symlink the whole directory
                    create_symlink(src, target)
                else:
                    # Recurse into directory
                    target.mkdir(parents=True, exist_ok=True)
                    process_dir(src, target)
            else:
                # Symlink the file
                create_symlink(src, target)

    process_dir(home_dir, Path.home())


def apply_chmod_config(directory: Path, chmod_config: dict[int | str, str | list[str]]) -> int:
    """Apply chmod settings from a .dotfiles.yaml config.

    Format:
        chmod:
          600:
            - "**/*"
          700:
            - "**/"
            - "*.sh"
    """
    count = 0
    for mode_str, globs in chmod_config.items():
        try:
            mode = int(str(mode_str), 8)
        except ValueError:
            print_warning(f"Invalid mode: {mode_str}")
            continue

        if isinstance(globs, str):
            globs = [globs]

        for pattern in globs:
            # Handle "." specially - chmod the directory itself
            if pattern == ".":
                try:
                    directory.chmod(mode)
                    count += 1
                except PermissionError:
                    print_warning(f"Permission denied: {directory}")
                continue

            # Pattern ending with / should only match directories
            dirs_only = pattern.endswith("/")
            glob_pattern = pattern.rstrip("/") if dirs_only else pattern

            for path in directory.glob(glob_pattern):
                if path.name in SKIP_FILES:
                    continue
                if dirs_only and not path.is_dir():
                    continue
                try:
                    path.chmod(mode)
                    count += 1
                except (PermissionError, FileNotFoundError):
                    pass  # Silently skip permission errors and broken symlinks

    return count


def fix_permissions(home_dir: Path) -> None:
    """Apply permissions based on .dotfiles.yaml config files."""
    print_step("Applying permissions from .dotfiles.yaml configs...")

    total = 0
    for config_file in home_dir.rglob(DOTFILES_CONFIG):
        try:
            config: dict[str, dict[int | str, str | list[str]]] = (
                yaml.safe_load(config_file.read_text()) or {}
            )
        except yaml.YAMLError as e:
            print_warning(f"Invalid YAML in {config_file}: {e}")
            continue

        chmod_config = config.get("chmod")
        if chmod_config:
            count = apply_chmod_config(config_file.parent, chmod_config)
            total += count

    if total:
        print_success(f"Applied chmod to {total} path(s)")
    else:
        print_step("No chmod configs found")


def setup_macos_app_configs() -> None:
    """Symlink macOS application config directories."""
    if not is_mac():
        return

    app_configs = [
        ("Apps/SublimeText3/User", "Library/Application Support/Sublime Text 3/Packages/User"),
        ("Apps/Code/User", "Library/Application Support/Code/User"),
    ]

    for dropbox_rel, target_rel in app_configs:
        src = DROPBOX_DIR / dropbox_rel
        target = Path.home() / target_rel

        if not src.is_dir():
            continue

        if target.is_symlink():
            print_step(f"{target} is already a symlink")
            continue

        # Backup existing directory
        if target.is_dir():
            import time
            backup = target.with_name(f"{target.name}_backup_{int(time.time())}")
            target.rename(backup)
            print_warning(f"Backed up {target} → {backup}")

        # Create parent directories
        target.parent.mkdir(parents=True, exist_ok=True)

        # Create symlink
        target.symlink_to(src)
        print_success(f"Linked {target} → {src}")


def check_stale_symlinks(home_dir: Path) -> None:
    """Warn about symlinks pointing to removed Dropbox dotfiles."""
    print_step("Checking for stale symlinks...")

    home = Path.home()
    stale: list[Path] = []

    def check_dir(directory: Path) -> None:
        """Recursively check for stale symlinks."""
        try:
            for path in directory.iterdir():
                if path.is_symlink():
                    # Check if symlink points into Dropbox dotfiles but target is gone
                    try:
                        target_str = str(path.readlink())
                    except OSError:
                        continue
                    if str(home_dir) in target_str and not path.exists():
                        stale.append(path)
                elif path.is_dir() and not path.is_symlink():
                    # Only recurse into real directories, not symlinked ones
                    check_dir(path)
        except PermissionError:
            pass

    # Check common dotfile locations
    for item in home.iterdir():
        if item.name.startswith(".") and item.is_symlink():
            try:
                target_str = str(item.readlink())
            except OSError:
                continue
            if str(home_dir) in target_str and not item.exists():
                stale.append(item)
        elif item.name.startswith(".") and item.is_dir() and not item.is_symlink():
            check_dir(item)

    if stale:
        print_warning(f"Found {len(stale)} stale symlink(s) pointing to removed Dropbox files:")
        for path in stale:
            print(f"  {path}")
        print("  Run 'rm <symlink>' to remove, or restore the file in Dropbox.")


def main() -> int:
    """Main entry point."""
    print_header("Setting up Dropbox dotfiles")

    # WSL support
    setup_wsl_dropbox()

    home_dir = DROPBOX_DIR / "dotfiles" / "home"

    if not home_dir.is_dir():
        print_warning("Dropbox dotfiles/home not found")
        print("Make sure Dropbox is installed and ~/Dropbox/dotfiles/home is synced.")
        print("Skipping Dropbox setup.")
        return 0

    check_stale_symlinks(home_dir)
    symlink_home_dir(home_dir)
    fix_permissions(home_dir)
    setup_macos_app_configs()

    # Also link scripts from Dropbox root if it exists
    scripts_dir = DROPBOX_DIR / "scripts"
    if scripts_dir.exists():
        create_symlink(scripts_dir, Path.home() / "scripts")

    print_success("Dropbox setup complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
