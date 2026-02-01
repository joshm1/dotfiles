#!/usr/bin/env python3
"""Setup Neovim."""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from urllib.request import urlretrieve

from dotfiles_scripts.setup_utils import (
    print_header,
    print_step,
    print_success,
    print_warning,
)

NVIM_VERSION = "nightly"


def get_nvim_info() -> tuple[str, Path]:
    """Get Neovim download info for current platform."""
    system = platform.system()
    machine = platform.machine()

    if system == "Darwin":
        archive = "nvim-macos-arm64.tar.gz" if machine == "arm64" else "nvim-macos-x86_64.tar.gz"
        install_dir = Path.home() / archive.replace(".tar.gz", "")
    elif system == "Linux":
        archive = "nvim-linux64.tar.gz"
        install_dir = Path.home() / "nvim-linux64"
    else:
        raise RuntimeError(f"Unsupported platform: {system}")

    return archive, install_dir


def download_neovim() -> bool:
    """Download and install Neovim nightly."""
    archive_name, install_dir = get_nvim_info()

    if install_dir.exists():
        print_success(f"Neovim already installed at {install_dir}")
        return True

    url = f"https://github.com/neovim/neovim/releases/download/{NVIM_VERSION}/{archive_name}"
    archive_path = Path.home() / archive_name

    print_step(f"Downloading Neovim {NVIM_VERSION}...")
    try:
        urlretrieve(url, archive_path)
    except Exception as e:
        print_warning(f"Failed to download Neovim: {e}")
        return False

    # Remove quarantine attribute on macOS
    if platform.system() == "Darwin":
        print_step("Removing quarantine attribute...")
        subprocess.run(["xattr", "-c", str(archive_path)], check=False)

    print_step("Extracting Neovim...")
    try:
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(path=Path.home())
    except Exception as e:
        print_warning(f"Failed to extract Neovim: {e}")
        return False

    # Cleanup
    archive_path.unlink()

    print_success(f"Neovim installed to {install_dir}")
    return True


def verify_neovim() -> bool:
    """Verify Neovim installation."""
    _, install_dir = get_nvim_info()
    nvim_bin = install_dir / "bin" / "nvim"

    if not nvim_bin.exists():
        # Check if nvim is in PATH (installed via homebrew or other means)
        if shutil.which("nvim"):
            print_success("Neovim found in PATH")
            result = subprocess.run(["nvim", "--version"], capture_output=True, text=True)
            print(f"  {result.stdout.splitlines()[0]}")
            return True

        print_warning("Neovim binary not found")
        return False

    print_success("Neovim binary found")
    result = subprocess.run([str(nvim_bin), "--version"], capture_output=True, text=True)
    print(f"  {result.stdout.splitlines()[0]}")

    print_step(f"Note: Make sure {install_dir}/bin is in your PATH")
    return True


def main() -> int:
    """Main entry point."""
    print_header("Setting up Neovim")

    download_neovim()
    verify_neovim()

    print_success("Neovim setup complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
