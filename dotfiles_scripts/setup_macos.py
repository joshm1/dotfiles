#!/usr/bin/env python3
"""Configure macOS system defaults."""

from __future__ import annotations

import platform
import sys

from dotfiles_scripts.setup_utils import (
    print_header,
    print_step,
    print_success,
    run_cmd,
)


def is_mac() -> bool:
    return platform.system() == "Darwin"


def main() -> int:
    """Main entry point."""
    if not is_mac():
        return 0

    print_header("Configuring macOS defaults")

    defaults = [
        # Disable press-and-hold for keys (enable key repeat)
        ("-g", "ApplePressAndHoldEnabled", "-bool", "false"),
        # Delay until key repeat (higher = longer delay; default ~25, range 15-120)
        ("-g", "InitialKeyRepeat", "-int", "25"),
        # Key repeat rate (lower = faster; default 2, range 1-6)
        ("-g", "KeyRepeat", "-int", "2"),
        # Show hidden files in Finder
        ("com.apple.finder", "AppleShowAllFiles", "YES"),
    ]

    for args in defaults:
        domain = args[0]
        key = args[1]
        print_step(f"Setting {domain} {key}...")
        run_cmd(["defaults", "write", *args], check=False)

    print_success("macOS defaults configured")
    print("  Note: Some changes may require logout/restart to take effect")

    return 0


if __name__ == "__main__":
    sys.exit(main())
