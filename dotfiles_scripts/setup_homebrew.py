#!/usr/bin/env python3
"""Setup Homebrew and install packages from Brewfiles."""

from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from dotfiles_scripts.setup_device_id import get_device_id
from dotfiles_scripts.setup_utils import (
    DOTFILES_REPO,
    DROPBOX_DIR,
    create_symlink,
    print_header,
    print_step,
    print_success,
    print_warning,
    run_cmd,
)


def is_homebrew_installed() -> bool:
    """Check if Homebrew is installed."""
    return shutil.which("brew") is not None


def install_homebrew() -> bool:
    """Install Homebrew."""
    print_step("Installing Homebrew...")

    install_script = "https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh"

    try:
        # Download and run the installer
        result = subprocess.run(
            f'curl -fsSL {install_script} | /bin/bash',
            shell=True,
            check=True,
        )

        # Add to zprofile
        zprofile = Path.home() / ".zprofile"
        brew_init = 'eval "$(/opt/homebrew/bin/brew shellenv)"'

        if zprofile.exists():
            content = zprofile.read_text()
            if brew_init not in content:
                with zprofile.open("a") as f:
                    f.write("\n# Set PATH, MANPATH, etc., for Homebrew.\n")
                    f.write(f"{brew_init}\n")
        else:
            zprofile.write_text(f"# Set PATH, MANPATH, etc., for Homebrew.\n{brew_init}\n")

        # Initialize for current session
        subprocess.run(
            ["/opt/homebrew/bin/brew", "shellenv"],
            capture_output=True,
        )

        print_success("Homebrew installed")
        return True

    except subprocess.CalledProcessError as e:
        print_warning(f"Failed to install Homebrew: {e}")
        return False


def get_brewfiles() -> list[Path]:
    """Get all Brewfiles to install, including device-specific ones from Dropbox."""
    brewfiles: list[Path] = []
    homebrew_dir = DOTFILES_REPO / "homebrew"

    # Get Brewfiles from dotfiles repo
    for brewfile in sorted(homebrew_dir.glob("Brewfile*")):
        if brewfile.name.startswith(".") or ".lock.json" in brewfile.name:
            continue
        brewfiles.append(brewfile)

    # Check for device-specific Brewfiles in Dropbox
    device_id = get_device_id()
    if device_id:
        dropbox_homebrew = DROPBOX_DIR / "dotfiles" / "homebrew"
        if dropbox_homebrew.exists():
            # Look for device-specific Brewfiles (e.g., Brewfile-macbook-pro)
            device_brewfile = dropbox_homebrew / f"Brewfile-{device_id}"
            if device_brewfile.exists():
                print_step(f"Found device-specific Brewfile: {device_brewfile}")
                brewfiles.append(device_brewfile)

            # Also look for any Brewfile-casks-{device_id}
            device_casks = dropbox_homebrew / f"Brewfile-casks-{device_id}"
            if device_casks.exists():
                print_step(f"Found device-specific casks: {device_casks}")
                brewfiles.append(device_casks)

    return brewfiles


def run_brew_bundle() -> bool:
    """Run brew bundle for all Brewfiles."""
    homebrew_dir = DOTFILES_REPO / "homebrew"
    installed_marker = homebrew_dir / ".installed"

    # Symlink main Brewfile to home
    main_brewfile = homebrew_dir / "Brewfile"
    if main_brewfile.exists():
        create_symlink(main_brewfile, Path.home() / "Brewfile")

    if installed_marker.exists():
        print_step("Homebrew bundle already run")
        print(f"  Delete {installed_marker} to run again")
        return True

    print_step("Running brew bundle...")

    brewfiles = get_brewfiles()
    for brewfile in brewfiles:
        print_step(f"Installing from {brewfile.name}...")
        try:
            run_cmd(["brew", "bundle", f"--file={brewfile}"])
        except subprocess.CalledProcessError:
            print_warning(f"Some packages from {brewfile.name} failed to install")

    # Mark as installed
    installed_marker.write_text(f"Installed: {datetime.now().isoformat()}\n")
    print_success("Homebrew bundle complete")

    return True


def main() -> int:
    """Main entry point."""
    print_header("Setting up Homebrew")

    if not is_homebrew_installed():
        if not install_homebrew():
            return 1
    else:
        print_success("Homebrew already installed")

    run_brew_bundle()

    print_success("Homebrew setup complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
