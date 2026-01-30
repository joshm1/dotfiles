#!/usr/bin/env python3
"""Setup Dropbox-synced dotfiles and private config files."""

from __future__ import annotations

import os
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

    # Get Windows username
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


def symlink_project_files() -> None:
    """Symlink project-specific files only if target directory exists."""
    projects_dir = DROPBOX_DIR / "dotfiles" / "projects"
    if not projects_dir.is_dir():
        return

    for src in projects_dir.rglob("*"):
        if not src.is_file():
            continue

        # Skip .DS_Store files
        if src.name == ".DS_Store":
            continue

        rel_path = src.relative_to(DROPBOX_DIR / "dotfiles")
        target = Path.home() / rel_path
        target_dir = target.parent

        if target_dir.is_dir():
            if target.exists() or target.is_symlink():
                target.unlink()
            target.symlink_to(src)
            print_success(f"Linked {target.name}")


def symlink_history_files() -> None:
    """Symlink shell history and config files from Dropbox."""
    # Note: .gitignore comes from home/ directory, not Dropbox
    history_files = [
        ".zsh_history",
        ".node_repl_history",
        ".python_history",
        ".psql_history",
        ".pry_history",
        ".npmrc",
        ".warprc",
    ]

    dropbox_dotfiles = DROPBOX_DIR / "dotfiles"

    for filename in history_files:
        src = dropbox_dotfiles / filename
        if src.exists():
            create_symlink(src, Path.home() / filename)


def symlink_secret_dirs() -> None:
    """Symlink directories containing secrets."""
    secret_dirs = [".aws", ".ssh", ".docker", ".kube"]

    dropbox_dotfiles = DROPBOX_DIR / "dotfiles"

    for dirname in secret_dirs:
        src = dropbox_dotfiles / dirname
        if src.exists():
            create_symlink(src, Path.home() / dirname)

    # Also link bin and scripts
    if (dropbox_dotfiles / "bin").exists():
        create_symlink(dropbox_dotfiles / "bin", Path.home() / "bin")

    if (DROPBOX_DIR / "scripts").exists():
        create_symlink(DROPBOX_DIR / "scripts", Path.home() / "scripts")


def fix_permissions() -> None:
    """Adjust permissions on secret files."""
    print_step("Adjusting permissions on secret files...")

    dropbox_dotfiles = DROPBOX_DIR / "dotfiles"

    # Docker config
    docker_config = dropbox_dotfiles / ".docker" / "config.json"
    if docker_config.exists():
        docker_config.chmod(0o600)

    # AWS - remove group/other permissions
    aws_dir = dropbox_dotfiles / ".aws"
    if aws_dir.exists():
        for path in aws_dir.rglob("*"):
            path.chmod(path.stat().st_mode & ~(stat.S_IRWXG | stat.S_IRWXO))

    # SSH
    ssh_dir = dropbox_dotfiles / ".ssh"
    if ssh_dir.exists():
        for path in ssh_dir.rglob("*"):
            if path.is_file():
                path.chmod(0o600)
            elif path.is_dir():
                path.chmod(0o700)

    # Kube
    kube_dir = dropbox_dotfiles / ".kube"
    if kube_dir.exists():
        for path in kube_dir.rglob("*"):
            path.chmod(path.stat().st_mode & ~(stat.S_IRWXG | stat.S_IRWXO))

    # Bin
    bin_dir = dropbox_dotfiles / "bin"
    if bin_dir.exists():
        for path in bin_dir.rglob("*"):
            if path.is_file():
                path.chmod(path.stat().st_mode & ~(stat.S_IRWXG | stat.S_IRWXO))

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

    dropbox_dotfiles = DROPBOX_DIR / "dotfiles"

    if not dropbox_dotfiles.is_dir():
        print_warning("Dropbox dotfiles not found")
        print("Make sure Dropbox is installed and ~/Dropbox/dotfiles is synced.")
        print("Skipping Dropbox setup.")
        return 0

    symlink_project_files()
    symlink_history_files()
    symlink_secret_dirs()
    fix_permissions()
    setup_macos_app_configs()

    print_success("Dropbox setup complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
