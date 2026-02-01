#!/usr/bin/env python3
"""Install neovim nightly from GitHub releases."""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from urllib.request import urlretrieve

from dotfiles_scripts.setup_utils import (
    print_header,
    print_step,
    print_success,
    print_warning,
    print_error,
)

INSTALL_DIR = Path("/opt/nvim")
SYMLINK_PATH = Path("/usr/local/bin/nvim")
NIGHTLY_URL_TEMPLATE = "https://github.com/neovim/neovim/releases/download/nightly/nvim-macos-{arch}.tar.gz"


def get_arch() -> str:
    """Get the architecture for the download URL."""
    machine = platform.machine()
    if machine == "arm64":
        return "arm64"
    elif machine == "x86_64":
        return "x86_64"
    else:
        raise RuntimeError(f"Unsupported architecture: {machine}")


def get_current_version() -> str | None:
    """Get the currently installed neovim version."""
    if not SYMLINK_PATH.exists():
        return None
    try:
        result = subprocess.run(
            [str(SYMLINK_PATH), "--version"],
            capture_output=True,
            text=True,
        )
        # First line is like "NVIM v0.11.0-dev-1234+gabcdef"
        first_line = result.stdout.split("\n")[0]
        return first_line.replace("NVIM ", "").strip()
    except Exception:
        return None


def download_nightly(arch: str) -> Path:
    """Download the nightly release and return path to tarball."""
    url = NIGHTLY_URL_TEMPLATE.format(arch=arch)
    print_step(f"Downloading from {url}")

    tmpdir = Path(tempfile.mkdtemp())
    tarball = tmpdir / "nvim.tar.gz"
    urlretrieve(url, tarball)

    return tarball


def install_neovim(tarball: Path) -> None:
    """Extract and install neovim."""
    print_step("Extracting tarball")

    tmpdir = tarball.parent
    with tarfile.open(tarball, "r:gz") as tar:
        tar.extractall(tmpdir)

    # Find extracted directory (nvim-macos-arm64 or nvim-macos-x86_64)
    extracted = None
    for item in tmpdir.iterdir():
        if item.is_dir() and item.name.startswith("nvim-"):
            extracted = item
            break

    if not extracted:
        raise RuntimeError("Could not find extracted neovim directory")

    # Remove existing installation
    if INSTALL_DIR.exists():
        print_step(f"Removing existing installation at {INSTALL_DIR}")
        shutil.rmtree(INSTALL_DIR)

    # Move to /opt/nvim (requires sudo)
    print_step(f"Installing to {INSTALL_DIR}")
    subprocess.run(
        ["sudo", "mv", str(extracted), str(INSTALL_DIR)],
        check=True,
    )

    # Create symlink
    print_step(f"Creating symlink at {SYMLINK_PATH}")
    SYMLINK_PATH.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["sudo", "ln", "-sf", str(INSTALL_DIR / "bin" / "nvim"), str(SYMLINK_PATH)],
        check=True,
    )


def main() -> int:
    """Main entry point."""
    print_header("Installing Neovim Nightly")

    if platform.system() != "Darwin":
        print_error("This script only supports macOS")
        return 1

    current = get_current_version()
    if current:
        print_step(f"Current version: {current}")

    try:
        arch = get_arch()
        print_step(f"Architecture: {arch}")

        tarball = download_nightly(arch)
        install_neovim(tarball)

        # Cleanup
        shutil.rmtree(tarball.parent)

        # Verify installation
        new_version = get_current_version()
        if new_version:
            print_success(f"Installed neovim {new_version}")
        else:
            print_warning("Installation completed but could not verify version")

        return 0

    except Exception as e:
        print_error(f"Installation failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
