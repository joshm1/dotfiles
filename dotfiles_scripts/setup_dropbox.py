#!/usr/bin/env python3
"""Setup Dropbox-synced dotfiles by symlinking from ~/Dropbox/dotfiles/home/ to $HOME."""

from __future__ import annotations

import platform
import stat
import subprocess
import sys
from pathlib import Path

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

# Files to skip when traversing
SKIP_FILES = {".DS_Store", SYMLINK_DIR_TAG}


def is_mac() -> bool:
    return platform.system() == "Darwin"


def is_wsl() -> bool:
    try:
        with open("/proc/version", "r") as f:
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


def fix_permissions(home_dir: Path) -> None:
    """Adjust permissions on secret files."""
    print_step("Adjusting permissions on secret files...")

    # AWS - remove group/other permissions
    aws_dir = home_dir / ".aws"
    if aws_dir.exists():
        for path in aws_dir.rglob("*"):
            if path.name == SYMLINK_DIR_TAG:
                continue
            path.chmod(path.stat().st_mode & ~(stat.S_IRWXG | stat.S_IRWXO))

    # SSH
    ssh_dir = home_dir / ".ssh"
    if ssh_dir.exists():
        for path in ssh_dir.rglob("*"):
            if path.name == SYMLINK_DIR_TAG:
                continue
            if path.is_file():
                path.chmod(0o600)
            elif path.is_dir():
                path.chmod(0o700)

    # Docker config
    docker_config = home_dir / ".docker" / "config.json"
    if docker_config.exists():
        docker_config.chmod(0o600)

    # Bin - make executable, remove group/other
    bin_dir = home_dir / "bin"
    if bin_dir.exists():
        for path in bin_dir.rglob("*"):
            if path.name == SYMLINK_DIR_TAG:
                continue
            if path.is_file():
                path.chmod(0o700)

    print_success("Permissions adjusted")


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
