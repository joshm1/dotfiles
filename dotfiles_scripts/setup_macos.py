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
        # Fast initial key repeat (normal minimum is 15 = 225ms)
        ("-g", "InitialKeyRepeat", "-int", "10"),
        # Fast key repeat (normal minimum is 2 = 30ms)
        ("-g", "KeyRepeat", "-int", "1"),
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
