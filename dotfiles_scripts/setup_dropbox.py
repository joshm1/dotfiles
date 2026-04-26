#!/usr/bin/env python3
"""Setup cloud-synced dotfiles by symlinking from ~/.dotfiles-private/home/ to $HOME.

``~/.dotfiles-private`` is a single, machine-local symlink that points at the
user's cloud-synced private dotfiles (Google Drive or Dropbox). Migrating
between clouds is a matter of retargeting this one symlink — every setup
script and the shell read through it, so they don't care which provider is
behind it. The filename is kept as ``setup_dropbox.py`` so the registered
``setup-dropbox`` console script and existing muscle memory keep working.
"""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

import yaml

from dotfiles_scripts.setup_device_id import get_device_id, get_hierarchy_levels
from dotfiles_scripts.setup_utils import (
    DROPBOX_DIR,
    PRIVATE_DOTFILES,
    SKIP_FILES,
    create_symlink,
    ensure_private_dotfiles_symlink,
    get_private_dotfiles,
    print_header,
    print_step,
    print_success,
    print_warning,
    symlink_home_dir,
)

# Config file for directory-specific settings
DOTFILES_CONFIG = ".dotfiles.yaml"


def is_mac() -> bool:
    return platform.system() == "Darwin"


def is_wsl() -> bool:
    try:
        with Path("/proc/version").open() as f:
            return "microsoft" in f.read().lower()
    except FileNotFoundError:
        return False


def setup_wsl_dropbox() -> None:
    """On WSL, create symlink to Windows Dropbox if needed.

    Note: WSL machines have not migrated to Google Drive — we still link the
    Windows Dropbox folder so cloud discovery picks it up via DROPBOX_DIR.
    """
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


def check_stale_symlinks(home_dir: Path) -> None:
    """Warn about symlinks pointing to removed cloud dotfiles."""
    print_step("Checking for stale symlinks...")

    home = Path.home()
    stale: list[Path] = []

    def check_dir(directory: Path) -> None:
        """Recursively check for stale symlinks."""
        try:
            for path in directory.iterdir():
                if path.is_symlink():
                    # Check if symlink points into the cloud dotfiles tree but target is gone
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
        print_warning(f"Found {len(stale)} stale symlink(s) pointing to removed cloud files:")
        for path in stale:
            print(f"  {path}")
        print("  Run 'rm <symlink>' to remove, or restore the file in your cloud folder.")


def create_device_zshrc_configs(home_dir: Path) -> None:
    """Create device-specific .zshrc.before and .zshrc.after hierarchy files if they don't exist."""
    device_id = get_device_id()
    if not device_id:
        return

    levels = get_hierarchy_levels(device_id)

    for base_name in (".zshrc.before", ".zshrc.after"):
        for level in levels:
            suffix = f".{level}" if level else ""
            config_file = home_dir / f"{base_name}{suffix}"

            if not config_file.exists():
                label = level if level else "all devices"
                config_file.write_text(
                    f"# {base_name} for {label}\n"
                    f"# Sourced by ~/.zshrc {'before' if 'before' in base_name else 'after'} main config\n"
                )
                print_success(f"Created {config_file}")


def create_device_gitconfigs(home_dir: Path) -> None:
    """Create device-specific gitconfig files with placeholder content if they don't exist."""
    device_id_file = Path.home() / ".device_id"
    if not device_id_file.exists():
        return

    device_id = device_id_file.read_text().strip()
    if not device_id:
        return

    placeholder = """\
# Device-specific git config
# Uncomment and set your signing key:
# [user]
#   signingkey = TODO
"""

    for src in home_dir.glob(".gitconfig_*"):
        # Skip files that already have a device_id suffix
        if src.name.endswith(f".{device_id}"):
            continue

        config_file = Path.home() / f"{src.name}.{device_id}"
        if not config_file.exists():
            config_file.write_text(placeholder)
            print_step(f"Created {config_file}")


def wait_for_cloud() -> Path | None:
    """Ensure ``~/.dotfiles-private`` resolves to a cloud-synced directory.

    Calls :func:`ensure_private_dotfiles_symlink` to (re)create the local
    pointer if a cloud provider is mounted but the symlink is missing. If no
    cloud provider can be found, prompts the user and re-tries until they
    skip or the symlink resolves. Returns the ``home`` subdirectory or
    ``None``.
    """
    home_dir = _resolve_home_dir()
    if home_dir is not None:
        return home_dir

    print_warning("~/.dotfiles-private is not pointing at a synced cloud directory")
    print("\nExpected the symlink to resolve to one of:")
    print(f"  {Path.home()}/Library/CloudStorage/GoogleDrive-*/My Drive/dotfiles-private")
    print(f"  {Path.home()}/Library/CloudStorage/GoogleDrive-*/My Drive/dotfiles")
    print(f"  {DROPBOX_DIR}/dotfiles")
    print("\nTo fix this:")
    print("  - Google Drive: install Google Drive for Desktop and sign in")
    print("  - Dropbox: brew install --cask dropbox && open -a Dropbox")
    print("  Then make sure the dotfiles folder is synced and available offline.")

    while True:
        try:
            response = input("\nPress Enter to check again, or 's' to skip: ").strip().lower()
            if response == "s":
                return None
            home_dir = _resolve_home_dir()
            if home_dir is not None:
                print_success(f"Cloud dotfiles found via {PRIVATE_DOTFILES} → {home_dir.parent}")
                return home_dir
            print_warning("Still not found. Make sure your cloud provider is synced...")
        except (EOFError, KeyboardInterrupt):
            print()
            raise SystemExit(0) from None


def _resolve_home_dir() -> Path | None:
    """Probe for a cloud root, (re)create the local symlink, and return ``home/``."""
    private = ensure_private_dotfiles_symlink()
    if private is None:
        return None
    home_dir = private / "home"
    return home_dir if home_dir.is_dir() else None


def check_cloud_sync(home_dir: Path) -> bool:
    """Check if cloud-synced files are actually downloaded vs online-only placeholders.

    Both Dropbox Smart Sync and Google Drive's "Stream files" mode can leave
    0-byte placeholder files that look present but have no content. This checks
    critical files to ensure they've been downloaded.
    """
    critical_files = [
        ".gitconfig_local",
        ".zshrc.before",
        ".zshrc.after",
    ]

    unsynced: list[Path] = []
    for name in critical_files:
        path = home_dir / name
        if path.exists() and path.stat().st_size == 0:
            unsynced.append(path)

    if not unsynced:
        return True

    print_warning("Cloud files appear to be online-only (0 bytes — not downloaded locally)")
    print("\n  Unsynced files:")
    for path in unsynced:
        print(f"    {path}")
    print("\n  To fix this:")
    print(f"    1. Open Finder and navigate to {home_dir.parent}")
    print("    2. Select all files (Cmd+A)")
    print("    3. Right-click → 'Make Available Offline' (Dropbox) or 'Available offline' (Google Drive)")

    while True:
        try:
            response = input("\nPress Enter to check again, or 's' to skip: ").strip().lower()
            if response == "s":
                return False
            # Re-check
            still_unsynced = [p for p in unsynced if p.stat().st_size == 0]
            if not still_unsynced:
                print_success("Cloud files are now synced!")
                return True
            print_warning(f"Still {len(still_unsynced)} file(s) unsynced...")
        except (EOFError, KeyboardInterrupt):
            print()
            raise SystemExit(0) from None


def main() -> int:
    """Main entry point."""
    print_header("Setting up cloud-synced dotfiles")

    # WSL support — symlinks ~/Dropbox to the Windows Dropbox folder so
    # cloud discovery (DROPBOX_DIR fallback) picks it up.
    setup_wsl_dropbox()

    home_dir = wait_for_cloud()
    if home_dir is None:
        print_step("Skipping cloud-synced dotfiles setup")
        return 0

    if not check_cloud_sync(home_dir):
        print_warning("Continuing with unsynced files — some configs may be empty")

    check_stale_symlinks(home_dir)
    create_device_zshrc_configs(home_dir)
    create_device_gitconfigs(home_dir)
    symlink_home_dir(home_dir)
    fix_permissions(home_dir)

    # Also link scripts/ from the cloud root (sibling of the private dotfiles
    # tree) if it exists. Resolves through the symlink so it works for any
    # cloud provider.
    private = get_private_dotfiles()
    if private is not None:
        scripts_dir = private.resolve().parent / "scripts"
        if scripts_dir.exists():
            create_symlink(scripts_dir, Path.home() / "scripts")

    print_success("Cloud-synced dotfiles setup complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
