#!/usr/bin/env python3
"""
Setup mise (modern version manager, replacement for asdf).

Tool versions are defined in ~/.config/mise/config.toml (symlinked from dotfiles).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def print_step(msg: str) -> None:
    print(f"→ {msg}")


def print_success(msg: str) -> None:
    print(f"✓ {msg}")


def print_warning(msg: str) -> None:
    print(f"⚠ {msg}")


def print_error(msg: str) -> None:
    print(f"✗ {msg}", file=sys.stderr)


def run_cmd(
    cmd: list[str],
    check: bool = True,
    capture: bool = False,
    cwd: Path | str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command."""
    if capture:
        return subprocess.run(
            cmd,
            check=check,
            capture_output=True,
            text=True,
            cwd=cwd,
        )
    else:
        return subprocess.run(
            cmd,
            check=check,
            text=True,
            cwd=cwd,
        )


def is_mise_installed() -> bool:
    """Check if mise is installed."""
    return shutil.which("mise") is not None


def install_mise_via_homebrew() -> bool:
    """Install mise using Homebrew."""
    if not shutil.which("brew"):
        print_error("Homebrew not found. Please install Homebrew first.")
        return False

    print_step("Installing mise via Homebrew...")
    try:
        run_cmd(["brew", "install", "mise"])
        print_success("mise installed")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to install mise: {e}")
        return False


def get_mise_path() -> str | None:
    """Get the path to mise binary."""
    paths = [
        shutil.which("mise"),
        "/opt/homebrew/bin/mise",
        "/usr/local/bin/mise",
        str(Path.home() / ".local" / "bin" / "mise"),
    ]
    for p in paths:
        if p and Path(p).exists():
            return p
    return None


def main() -> int:
    """Main entry point."""
    print("=" * 50)
    print("  Setting up mise (version manager)")
    print("=" * 50)
    print()

    # Check/install mise
    if not is_mise_installed():
        print_step("mise not found, installing...")
        if not install_mise_via_homebrew():
            return 1
    else:
        print_success("mise already installed")

    mise_path = get_mise_path()
    if not mise_path:
        print_error("Could not find mise binary after installation")
        return 1

    # Show mise version
    result = run_cmd([mise_path, "--version"], capture=True)
    print(f"  mise version: {result.stdout.strip()}")
    print()

    # Trust the dotfiles directory
    dotfiles = Path.home() / ".dotfiles"
    if dotfiles.exists():
        print_step(f"Trusting {dotfiles} for mise config...")
        run_cmd([mise_path, "trust", str(dotfiles)], check=False)

    # Install tools from dotfiles and global config
    for cwd in [dotfiles, Path.home()]:
        if cwd.exists():
            print_step(f"Installing tools from {cwd}...")
            try:
                run_cmd([mise_path, "install"], cwd=cwd)
                print_success(f"Tools installed from {cwd}")
            except subprocess.CalledProcessError as e:
                print_warning(f"Some tools may have failed to install: {e}")

    # Show what's installed
    print("\nInstalled tools:")
    run_cmd([mise_path, "ls"])

    print()
    print_success("mise setup complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
